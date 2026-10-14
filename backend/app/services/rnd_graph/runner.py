"""langgraph 引擎执行入口（v2.1 §C.2/§C.4/§C.6）。

职责（只做编排与收尾，不复制业务逻辑）：
1. 校验引擎 pin（必须是 ``langgraph``；legacy 的 Run 永不进入本路径）；
2. 领取 Run 级租约锁（存在锁行即放弃投递并 WARN，不改 Run 状态、不接管）；
3. ``graph.invoke(initial_state, config, durability="sync")`` 首次执行；
   仅满足 5 项前置时用 ``graph.invoke(None, config, ...)`` 从 checkpoint 恢复（隔离环境专用）；
4. 成功收尾复用 ``_apply_run_success``、失败收尾复用 ``_apply_run_failure``（run=failed + 固定骨架 +
   ``workflow_session.status=active`` + 上抛），**不自动续跑、不静默降级**；
5. ``related_graph_snapshots`` 从 ``workflow_step_run``（按 sequence）非空 ``graph_snapshot_id`` 派生；
   ``final_report`` 由既有 ``_assemble_final_report``（经 ``_apply_run_success``）组装。

invoke 语义（**锁定版本实测签名**，2026-10-15 在服务器暂存树实测；v2.1 §C.4 要求记录）：

- ``langgraph==1.2.15`` / ``langgraph-checkpoint-postgres==3.1.3`` / ``langgraph-checkpoint==4.3.0`` /
  ``psycopg==3.2.9`` / ``psycopg-pool==3.3.3`` / Python 3.11.6。
- 实测 ``CompiledStateGraph.invoke`` 签名::

      invoke(self, input, config=None, *, context=None, stream_mode="values", print_mode=(),
             output_keys=None, interrupt_before=None, interrupt_after=None,
             durability=None, control=None, version="v1", **kwargs)

  ⇒ 本版本**支持** ``durability="sync"``（同步落盘）与 ``context=RunContext(...)``；
  ``Runtime[RunContext]`` 注入（``context_schema=RunContext``）实测可用
  （``langgraph.runtime.Runtime`` 的 ``context`` 即传给 ``invoke`` 的对象）。
- ``PostgresSaver.__init__(conn: Connection | ConnectionPool, pipe=None, serde=None)``；
  建表用 ``PostgresSaver.setup()``（仅 CLI 调用，autocommit）。
- 版本升级规则：``langgraph`` 与 ``langgraph-checkpoint-postgres`` 必须成对升级（二者共同约束
  ``langgraph-checkpoint>=4.3.0,<5.0.0``），并重跑 ``scripts/accept_rnd_engine_parity.py`` 与暂存自检。
"""

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.db.sqlalchemy import SessionLocal
from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository
from app.services import rnd_engine
from app.services.deepseek_client import DeepSeekClient
from app.services.rnd_graph import run_lock
from app.services.rnd_graph.context import RunContext
from app.services.rnd_graph.state import (
    AGENT_STATE_KEYS,
    initial_state,
    json_incompatible_paths,
)
from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator

logger = logging.getLogger(__name__)


class ResumePreconditionError(RuntimeError):
    """恢复前置未满足（v2.1 §C.4 的 5 项前置）。"""


def make_owner_token() -> str:
    """租约持有者标识：host:pid:随机后缀（足以区分同机多进程/多线程投递）。"""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"


def build_checkpointer():  # pragma: no cover - 生产路径；隔离环境注入替身（可 monkeypatch）
    """Checkpointer 工厂（可替换点：验收脚本注入异常注入型 Saver）。"""
    from app.services.rnd_graph.checkpointer import build_checkpointer as _build

    return _build()


def build_graph(checkpointer: Any = None):  # pragma: no cover - 生产路径
    """构建六步线性图（可替换点：验收脚本可注入自定义 checkpointer）。"""
    from app.services.rnd_graph.graph import build_rnd_graph

    return build_rnd_graph(checkpointer=checkpointer)


def _graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _load_run_snapshot(run_id: str) -> dict[str, Any]:
    """只读取 Run/Session 的输入字段（短会话）。"""
    db = SessionLocal()
    try:
        repository = PostgresRepository(db)
        run = repository.get_workflow_run(run_id)
        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")
        workflow_session = repository.get_workflow_session(run.session_id)
        if workflow_session is None:
            raise ValueError(f"Workflow session not found: {run.session_id}")
        return {
            "run_id": run.id,
            "session_id": run.session_id,
            "question": run.question,
            "brief": run.brief or {},
        }
    finally:
        db.close()


def _mark_run_running(run_id: str, session_id: str) -> None:
    """进入执行前把 Run/Session 置 running（与 legacy ``resume_run`` 开头语义一致，前端轮询可见）。"""
    db = SessionLocal()
    try:
        repository = PostgresRepository(db)
        run = repository.get_workflow_run(run_id)
        workflow_session = repository.get_workflow_session(session_id)
        if run is None or workflow_session is None:
            raise ValueError(f"缺少 Run/Session：run_id={run_id} session_id={session_id}")
        run.status = "running"
        workflow_session.status = "running"
        db.commit()
    finally:
        db.close()


def _committed_step_keys(run_id: str) -> list[str]:
    """已提交 completed step 行的 agent_key（按 sequence 升序）。"""
    db = SessionLocal()
    try:
        steps = PostgresRepository(db).list_workflow_step_runs(run_id)
        return [step.agent_key for step in steps if step.status == "completed"]
    finally:
        db.close()


def _checkpoint_completed_keys(checkpointer: Any, config: dict[str, Any]) -> set[str]:
    """checkpoint 里已落盘的 Agent 通道（``channel_versions`` 覆盖的 State Agent 字段）。"""
    checkpoint_tuple = checkpointer.get_tuple(config)
    if checkpoint_tuple is None:
        return set()
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    channels = set((checkpoint.get("channel_versions") or {}).keys())
    return {key for key in AGENT_STATE_KEYS if key in channels}


def assert_resume_preconditions(
    *,
    run_id: str,
    checkpointer: Any,
    config: dict[str, Any],
    recover_enabled: bool,
    engine_pin: str | None,
) -> dict[str, Any]:
    """5 项恢复前置（全部满足才允许 ``invoke(None, ...)``）。

    1. 该 run_id 存在 checkpoint，且最后 checkpoint 的通道覆盖已提交 step；
    2. 无其他存活 owner（由租约领取保证：领取失败即放弃，不进入本函数）；
    3. 显式恢复开关开启（隔离环境专用；生产恒关）；
    4. 已提交 StepRun 与 checkpoint state 一致（不一致 → 拒绝恢复并告警）；
    5. 引擎 pin = langgraph。
    """
    detail: dict[str, Any] = {"recover_enabled": recover_enabled, "engine_pin": engine_pin}
    # 前置 3：显式恢复开关（隔离环境专用；生产恒关）
    if not recover_enabled:
        raise ResumePreconditionError(
            "恢复开关未开启（settings.rnd_langgraph_resume_enabled / recover_enabled=false），拒绝 invoke(None)"
        )
    # 前置 5：pin = langgraph
    if engine_pin != rnd_engine.ENGINE_LANGGRAPH:
        raise ResumePreconditionError(f"引擎 pin != langgraph（实际 {engine_pin}）")
    # 前置 1：存在 checkpoint
    checkpoint_tuple = checkpointer.get_tuple(config)
    if checkpoint_tuple is None:
        raise ResumePreconditionError("该 run_id 无 checkpoint，无法恢复（必须用 invoke(initial_state, ...)）")
    # 前置 4：已提交 StepRun 与 checkpoint 一致（允许 W1 的"已提交但 checkpoint 未写"至多一步）
    committed = _committed_step_keys(run_id)
    checkpoint_keys = _checkpoint_completed_keys(checkpointer, config)
    order = _step_order()
    _assert_committed_matches_checkpoint(committed, checkpoint_keys, order)
    detail.update({"committed_steps": committed, "checkpoint_steps": sorted(checkpoint_keys)})
    return detail


def _step_order() -> tuple[str, ...]:
    from app.services.rnd_graph.graph import step_keys

    return step_keys()


def _assert_committed_matches_checkpoint(committed: list[str], checkpoint_keys: set[str], order: tuple[str, ...]) -> None:
    """一致性判定（v2.1 §C.4 前置 4 + W1 崩溃窗口）：

    - 已提交 step 必须是线性顺序的**前缀**（不得跳步/乱序）；
    - checkpoint 覆盖的 Agent 必须都已提交（不得出现"checkpoint 有、step 行无"）；
    - 已提交但未落 checkpoint 的最多**一个**（W1：节点已提交 step 行、checkpoint 尚未写，
      恢复时由节点入口守卫复用该步输出）。
    """
    ordered_committed = [key for key in order if key in set(committed)]
    if ordered_committed != list(committed):
        raise ResumePreconditionError(
            f"已提交 StepRun 不是线性前缀，拒绝恢复：committed={committed} order={list(order)}"
        )
    if not checkpoint_keys.issubset(set(committed)):
        raise ResumePreconditionError(
            f"checkpoint 覆盖了未提交的 Agent，拒绝恢复：checkpoint={sorted(checkpoint_keys)} committed={committed}"
        )
    frontier = max((order.index(key) for key in checkpoint_keys), default=-1)
    allowed_extra = {order[frontier + 1]} if frontier + 1 < len(order) else set()
    extra = set(committed) - set(checkpoint_keys)
    if not extra.issubset(allowed_extra):
        raise ResumePreconditionError(
            f"已提交 StepRun 与 checkpoint 不一致（超出 W1 单步窗口），拒绝恢复："
            f"committed={committed} checkpoint={sorted(checkpoint_keys)} allowed_extra={sorted(allowed_extra)}"
        )


def mark_run_failed(run_id: str, exc: BaseException, *, context: str = "langgraph 执行失败") -> None:
    """失败收尾：复用 legacy 失败语义（run=failed + 固定骨架 + session.status=active）。"""
    db = SessionLocal()
    try:
        repository = PostgresRepository(db)
        run = repository.get_workflow_run(run_id)
        if run is None:
            logger.error("失败收尾找不到 Run run_id=%s（%s）", run_id, context)
            return
        workflow_session = repository.get_workflow_session(run.session_id)
        if workflow_session is None:
            logger.error("失败收尾找不到 WorkflowSession run_id=%s（%s）", run_id, context)
            return
        related = [step.graph_snapshot_id for step in repository.list_workflow_step_runs(run_id) if step.graph_snapshot_id]
        orchestrator = RnDWorkflowOrchestrator(repository, None, None)  # 仅用仓储，不触 neo4j/LLM
        orchestrator._apply_run_failure(run, workflow_session, exc, related)
    except Exception:  # pragma: no cover - 失败收尾自身异常只记录，不掩盖原始异常
        db.rollback()
        logger.exception("失败收尾写入失败 run_id=%s（%s）", run_id, context)
    finally:
        db.close()


def _apply_success(run_id: str, session_id: str, final_state: dict[str, Any], llm_client: Any) -> dict[str, Any]:
    """成功收尾：派生快照列表 + 复用 ``_apply_run_success``（读六条 step 行组装 final_report）。"""
    db = SessionLocal()
    try:
        repository = PostgresRepository(db)
        run = repository.get_workflow_run(run_id)
        workflow_session = repository.get_workflow_session(session_id)
        if run is None or workflow_session is None:
            raise ValueError(f"成功收尾缺少 Run/Session：run_id={run_id} session_id={session_id}")
        related = [step.graph_snapshot_id for step in repository.list_workflow_step_runs(run_id) if step.graph_snapshot_id]
        orchestrator = RnDWorkflowOrchestrator(repository, None, llm_client)
        outcome = orchestrator._apply_run_success(
            run,
            workflow_session,
            final_master_payload=final_state["master_control_final"]["output_payload"],
            formula_result=final_state["formula_generation"],
            efficacy_result=final_state["efficacy_prediction"],
            flavor_result=final_state["flavor_prediction"],
            replacement_result=final_state["replacement_mapping"],
            related_graph_snapshots=related,
        )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "brief": run.brief,
            "final_report": outcome["final_report"],
            "steps": outcome["steps"],
            "summary_metrics": outcome["summary_metrics"],
            "related_graph_snapshots": related,
            "status": run.status,
        }
    finally:
        db.close()


def run_langgraph(
    run_id: str,
    *,
    resume: bool = False,
    recover_enabled: bool | None = None,
) -> dict[str, Any]:
    """执行一次 langgraph Run（首次执行或隔离环境手动恢复）。

    - 首次执行：``invoke(initial_state, config, durability="sync")``；
    - 恢复：仅当 5 项前置全部满足时 ``invoke(None, config, durability="sync")``；
    - 任何异常：失败收尾后**上抛**（与 legacy 一致，不自动续跑、不静默降级）。
    """
    recover_flag = settings.rnd_langgraph_resume_enabled if recover_enabled is None else bool(recover_enabled)
    snapshot = _load_run_snapshot(run_id)
    session_id = snapshot["session_id"]

    db = SessionLocal()
    try:
        engine_pin = rnd_engine.read_run_engine(db, run_id)
    except Exception as exc:
        # 读 pin 出错：Run 置 failed + 骨架 + ERROR 日志，不降级
        logger.exception("langgraph 读取引擎 pin 失败 run_id=%s", run_id)
        mark_run_failed(run_id, exc, context="读取 langgraph.run_engine 失败")
        raise
    finally:
        db.close()

    if engine_pin != rnd_engine.ENGINE_LANGGRAPH:
        error = f"引擎 pin 不是 langgraph（实际 {engine_pin!r}），拒绝进入 langgraph 路径"
        logger.error("%s run_id=%s", error, run_id)
        mark_run_failed(run_id, RuntimeError(error), context="引擎 pin 校验失败")
        raise RuntimeError(error)

    owner_token = make_owner_token()
    context = RunContext(
        session_factory=SessionLocal,
        neo4j_factory=Neo4jRepository,
        llm_client=DeepSeekClient(),
        owner_token=owner_token,
        run_id=run_id,
        session_id=session_id,
    )

    lock_db = SessionLocal()
    try:
        acquired = run_lock.acquire_lock(lock_db, run_id, owner_token)
        lock_db.commit()
        if not acquired:
            existing = run_lock.read_lock(lock_db, run_id)
            run_lock.log_lock_skipped(run_id, owner_token, existing)
            return {"run_id": run_id, "status": "skipped", "reason": "run_lock_held"}
    except Exception as exc:
        lock_db.rollback()
        # 锁表缺失/连库失败：明确失败，不降级
        logger.exception("langgraph 领取租约失败 run_id=%s", run_id)
        mark_run_failed(run_id, exc, context="领取 langgraph.run_lock 失败")
        raise
    finally:
        lock_db.close()

    heartbeat = run_lock.LeaseHeartbeat(SessionLocal, run_id, owner_token)
    heartbeat.start()
    try:
        # 取得执行权后再置 running（放弃投递不得改动 Run 状态）
        _mark_run_running(run_id, session_id)
        checkpointer = build_checkpointer()
        graph = build_graph(checkpointer=checkpointer)
        config = _graph_config(run_id)

        if resume:
            detail = assert_resume_preconditions(
                run_id=run_id,
                checkpointer=checkpointer,
                config=config,
                recover_enabled=recover_flag,
                engine_pin=engine_pin,
            )
            logger.info(
                "langgraph 恢复执行 run_id=%s session_id=%s committed_steps=%s checkpoint_steps=%s",
                run_id,
                session_id,
                detail.get("committed_steps"),
                detail.get("checkpoint_steps"),
            )
            invoke_input: Any = None
        else:
            invoke_input = initial_state(
                run_id=run_id,
                session_id=session_id,
                question=snapshot["question"],
                brief=snapshot["brief"],
            )
            incompatible = json_incompatible_paths(invoke_input)
            if incompatible:  # pragma: no cover - JSONB 来源数据理论上必然兼容
                logger.warning("langgraph 初始 State 存在非 JSON 兼容值 run_id=%s paths=%s", run_id, incompatible)

        logger.info(
            "langgraph invoke 开始 run_id=%s session_id=%s resume=%s owner=%s",
            run_id,
            session_id,
            resume,
            owner_token,
        )
        final_state = graph.invoke(invoke_input, config, context=context, durability="sync")
        result = _apply_success(run_id, session_id, final_state, context.llm_client)
        logger.info(
            "langgraph invoke 完成 run_id=%s session_id=%s status=%s steps=%s snapshots=%s",
            run_id,
            session_id,
            result.get("status"),
            len(result.get("steps") or []),
            len(result.get("related_graph_snapshots") or []),
        )
        return result
    except Exception as exc:
        logger.exception("langgraph 执行失败 run_id=%s session_id=%s", run_id, session_id)
        mark_run_failed(run_id, exc, context="langgraph 节点执行失败")
        raise
    finally:
        heartbeat.stop()
        _release_lock(run_id, owner_token)


def _release_lock(run_id: str, owner_token: str) -> None:
    db = SessionLocal()
    try:
        released = run_lock.release_lock(db, run_id, owner_token)
        db.commit()
        logger.info("langgraph 租约释放 run_id=%s owner=%s released=%s", run_id, owner_token, released)
    except Exception:  # pragma: no cover - 释放失败只告警（人工处理见 §C.3）
        db.rollback()
        logger.warning("langgraph 租约释放失败 run_id=%s owner=%s", run_id, owner_token, exc_info=True)
    finally:
        db.close()


def sweep_orphan_runs(*, stale_minutes: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    """W3 孤儿清扫（默认关闭）：仅把**超时的 langgraph Run** 标 ``failed`` + 骨架，**不自动续跑**。

    - ``settings.rnd_orphan_sweep_enabled`` 为 False 时直接返回 ``enabled=False``（默认安全）；
    - 仅作用于 pin=langgraph 的 Run（legacy Run 一律不动，保持 legacy 行为不变）。
    """
    if not settings.rnd_orphan_sweep_enabled:
        return {"enabled": False, "stale_minutes": None, "scanned": 0, "failed": [], "dry_run": dry_run}
    minutes = int(stale_minutes if stale_minutes is not None else settings.rnd_orphan_stale_minutes)
    threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes)
    db = SessionLocal()
    try:
        from sqlalchemy import text

        from app.db.langgraph_schema import resolve_schema

        schema = resolve_schema()
        sql = text(
            f"SELECT r.id AS run_id, r.session_id AS session_id, r.created_at AS created_at "
            f"FROM workflow_run r JOIN {schema}.run_engine p ON p.run_id = r.id "
            "WHERE p.engine = :engine AND r.status IN ('queued', 'running') AND r.created_at < :threshold "
            "ORDER BY r.created_at ASC"
        )
        rows = db.execute(
            sql, {"engine": rnd_engine.ENGINE_LANGGRAPH, "threshold": threshold}
        ).mappings().all()
        orphans = [dict(row) for row in rows]
    except Exception:
        db.rollback()
        logger.exception("孤儿清扫查询失败（已跳过本次清扫）")
        return {"enabled": True, "stale_minutes": minutes, "scanned": 0, "failed": [], "dry_run": dry_run, "error": True}
    finally:
        db.close()

    failed: list[str] = []
    if not dry_run and orphans:
        for orphan in orphans:
            error = RuntimeError(
                f"Run 超过 {minutes} 分钟仍处于 {orphan.get('created_at')} 起的状态（进程崩溃窗口 W3）："
                "阶段一不自动续跑，标记 failed"
            )
            mark_run_failed(str(orphan["run_id"]), error, context="孤儿清扫（W3）")
            failed.append(str(orphan["run_id"]))
    return {
        "enabled": True,
        "stale_minutes": minutes,
        "threshold": threshold.isoformat(),
        "scanned": len(orphans),
        "orphans": [str(item["run_id"]) for item in orphans],
        "failed": failed,
        "dry_run": dry_run,
    }
