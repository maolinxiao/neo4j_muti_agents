"""六个 Node 的工厂：只做胶水（v2.1 §B.1/§C.4）。

职责边界（严格）：
- 只包装既有的 ``RnDWorkflowOrchestrator._run_master_control`` /
  ``_run_formula_generation`` / ``_run_efficacy_prediction`` / ``_run_flavor_prediction`` /
  ``_run_replacement_mapping`` / ``_run_master_control_final``（后两者为本阶段新增的两个 master 步包装方法）；
- 组方、KB5 检索、KB4 替代、兜底、``_assemble_final_report``、KB5 回注、提示词/启停/耗时逻辑
  全部留在 orchestrator 与 ``_run_step`` 中，这里一行都不复制；
- 每个 Node 自开短会话（``RunContext.session_factory``），``finally`` 关闭；不跨节点共享 Session；
- 节点入口幂等守卫：``(run_id, agent_key)`` 已有 ``completed`` step 行则复用其
  ``output_payload`` / ``graph_snapshot_id``，不再调用 LLM、不新增行，日志 ``reused=true``（崩溃窗口 W1）；
- 成功路径上 step 行先由 ``_run_step`` 提交，节点返回后 LangGraph 才写 checkpoint（先提交 step 行再写 checkpoint）。
"""

import logging
from typing import TYPE_CHECKING, Any, Callable

from app.repositories.postgres_repository import PostgresRepository
from app.services.rnd_graph.context import RunContext
from app.services.rnd_graph.state import AGENT_STATE_KEYS
from app.services.rnd_workflow_orchestrator import AGENT_STEP_DEFS, RnDWorkflowOrchestrator

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查期
    from langgraph.runtime import Runtime

try:  # pragma: no cover - 取决于运行环境是否装了 langgraph
    from langgraph.runtime import Runtime  # type: ignore[assignment]
except ModuleNotFoundError:  # 本地未安装 langgraph 时：占位类型，仅用于函数注解
    TContext = Any

    class Runtime:  # type: ignore[no-redef]
        """langgraph 缺失时的注解占位（真正构建图时必须安装 langgraph）。"""

        def __class_getitem__(cls, item: Any) -> Any:
            return cls


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 顺序/依赖：全部从 AGENT_STEP_DEFS 派生，禁止在节点里写死 1..6
# ----------------------------------------------------------------------
SEQ_BY_AGENT: dict[str, int] = {step.agent_key: step.sequence for step in AGENT_STEP_DEFS}


def sequence_of(agent_key: str) -> int:
    """取某 Agent 的 sequence（唯一来源 = AGENT_STEP_DEFS）。"""
    try:
        return SEQ_BY_AGENT[agent_key]
    except KeyError as exc:  # pragma: no cover - 注册表与节点不一致时立即暴露
        raise KeyError(f"未知 agent_key：{agent_key}") from exc


def _existing_completed_step(orchestrator: RnDWorkflowOrchestrator, run_id: str, agent_key: str) -> Any | None:
    """幂等守卫：返回已提交的 completed step 行（无则 None）。

    复用既有仓储方法 ``list_workflow_step_runs``（按 sequence 升序），不新增仓储方法。
    """
    completed = [
        step
        for step in orchestrator.postgres_repository.list_workflow_step_runs(run_id)
        if step.agent_key == agent_key and step.status == "completed"
    ]
    if len(completed) > 1:
        logger.warning(
            "rnd_graph 幂等守卫发现重复 completed step 行 run_id=%s agent_key=%s count=%s（取首条）",
            run_id,
            agent_key,
            len(completed),
        )
    return completed[0] if completed else None


def _reused_result(step: Any) -> dict[str, Any]:
    """把已提交的 step 行还原为 ``_run_step`` 的返回形状。"""
    return {
        "step_id": step.id,
        "graph_snapshot_id": step.graph_snapshot_id,
        "output_payload": step.output_payload or {},
        "used_fallback": bool(step.used_fallback),
        "skipped": bool(step.skipped),
        "reused": True,
    }


def execute_step(
    runtime: "Runtime[RunContext]",
    agent_key: str,
    run_id: str,
    session_id: str,
    caller: Callable[[RnDWorkflowOrchestrator], dict[str, Any]],
) -> dict[str, Any]:
    """通用节点主体：短会话 + 幂等守卫 + 调用既有 ``_run_*``。"""
    context: RunContext = runtime.context
    db = context.session_factory()
    neo4j = context.neo4j_factory()
    try:
        orchestrator = RnDWorkflowOrchestrator(PostgresRepository(db), neo4j, context.llm_client)
        existing = _existing_completed_step(orchestrator, run_id, agent_key)
        if existing is not None:
            logger.info(
                "rnd_graph node reused=true run_id=%s session_id=%s agent_key=%s sequence=%s snapshot_id=%s",
                run_id,
                session_id,
                agent_key,
                sequence_of(agent_key),
                existing.graph_snapshot_id,
            )
            return _reused_result(existing)
        result = caller(orchestrator)
        result["reused"] = False
        # 日志字段白名单（v2.1 §E.9）：只记录 run/session/agent/sequence/兜底标记，不记录问题原文与 brief
        logger.info(
            "rnd_graph node reused=false run_id=%s session_id=%s agent_key=%s sequence=%s used_fallback=%s skipped=%s",
            run_id,
            session_id,
            agent_key,
            sequence_of(agent_key),
            result.get("used_fallback"),
            result.get("skipped"),
        )
        return result
    finally:
        try:
            neo4j.close()
        except Exception:  # pragma: no cover - 共享 driver 的 close 是 no-op，这里保证不外抛
            logger.warning("rnd_graph node neo4j close 失败 agent_key=%s", agent_key, exc_info=True)
        db.close()


# ----------------------------------------------------------------------
# 六个 Node（顺序 1..6 来自 AGENT_STEP_DEFS）
# ----------------------------------------------------------------------
def master_control_node(state: dict[str, Any], runtime: "Runtime[RunContext]") -> dict[str, Any]:
    run_id = state["run_id"]
    result = execute_step(
        runtime,
        "master_control",
        run_id,
        state["session_id"],
        lambda orchestrator: orchestrator._run_master_control(
            run_id,
            sequence_of("master_control"),
            state["brief"],
            state["question"],
        ),
    )
    return {"master_control": result}


def formula_generation_node(state: dict[str, Any], runtime: "Runtime[RunContext]") -> dict[str, Any]:
    run_id = state["run_id"]
    session_id = state["session_id"]
    result = execute_step(
        runtime,
        "formula_generation",
        run_id,
        session_id,
        lambda orchestrator: orchestrator._run_formula_generation(
            session_id,
            run_id,
            sequence_of("formula_generation"),
            state["brief"],
        ),
    )
    return {"formula_generation": result}


def efficacy_prediction_node(state: dict[str, Any], runtime: "Runtime[RunContext]") -> dict[str, Any]:
    run_id = state["run_id"]
    session_id = state["session_id"]
    result = execute_step(
        runtime,
        "efficacy_prediction",
        run_id,
        session_id,
        lambda orchestrator: orchestrator._run_efficacy_prediction(
            session_id,
            run_id,
            sequence_of("efficacy_prediction"),
            state["brief"],
            state["formula_generation"],
        ),
    )
    return {"efficacy_prediction": result}


def flavor_prediction_node(state: dict[str, Any], runtime: "Runtime[RunContext]") -> dict[str, Any]:
    run_id = state["run_id"]
    session_id = state["session_id"]
    result = execute_step(
        runtime,
        "flavor_prediction",
        run_id,
        session_id,
        lambda orchestrator: orchestrator._run_flavor_prediction(
            session_id,
            run_id,
            sequence_of("flavor_prediction"),
            state["brief"],
            state["formula_generation"],
        ),
    )
    return {"flavor_prediction": result}


def replacement_mapping_node(state: dict[str, Any], runtime: "Runtime[RunContext]") -> dict[str, Any]:
    run_id = state["run_id"]
    session_id = state["session_id"]
    result = execute_step(
        runtime,
        "replacement_mapping",
        run_id,
        session_id,
        lambda orchestrator: orchestrator._run_replacement_mapping(
            session_id,
            run_id,
            sequence_of("replacement_mapping"),
            state["brief"],
            state["formula_generation"],
            state["efficacy_prediction"],
            state["flavor_prediction"],
        ),
    )
    return {"replacement_mapping": result}


def master_control_final_node(state: dict[str, Any], runtime: "Runtime[RunContext]") -> dict[str, Any]:
    run_id = state["run_id"]
    result = execute_step(
        runtime,
        "master_control_final",
        run_id,
        state["session_id"],
        lambda orchestrator: orchestrator._run_master_control_final(
            run_id,
            sequence_of("master_control_final"),
            state["brief"],
            state["question"],
            master_initial=state["master_control"],
            formula_result=state["formula_generation"],
            efficacy_result=state["efficacy_prediction"],
            flavor_result=state["flavor_prediction"],
            replacement_result=state["replacement_mapping"],
        ),
    )
    return {"master_control_final": result}


NODE_FACTORIES: dict[str, Callable[..., dict[str, Any]]] = {
    "master_control": master_control_node,
    "formula_generation": formula_generation_node,
    "efficacy_prediction": efficacy_prediction_node,
    "flavor_prediction": flavor_prediction_node,
    "replacement_mapping": replacement_mapping_node,
    "master_control_final": master_control_final_node,
}

#: 图与 State 的一致性硬约束：两者必须覆盖同一组 Agent 键
assert set(NODE_FACTORIES) == set(AGENT_STATE_KEYS), "rnd_graph 节点集合与 RndGraphState 字段不一致"
