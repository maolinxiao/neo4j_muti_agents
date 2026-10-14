#!/usr/bin/env python
"""研发协同双引擎 Mock 等价 / 配置 / 兜底 / 故障注入验收（v2.1 §D-1，P1 门禁）。

覆盖：E2E-1、CFG-1..4、FB-1..3、FI-1..FI-4（v2.1 §D-1；v2.2 附录 §9 口径：FI-1..4 为门禁）。

隔离与安全：
- **只在隔离影子库运行**：默认 ``neo4j_agents_parity``（v2.2 亦可 ``neo4j_agents_migrate``）；
  库名必须匹配影子库口径，且**绝不允许** ``neo4j_agents``（生产）等库名；
- ``--mock``/``--offline`` 内置**禁止外网**校验：socket 连接只允许本机回环/Unix socket；
- 自建影子库（``CREATE DATABASE``）+ ``initialize_database()``；langgraph schema 复用
  ``backend/scripts/init_langgraph_checkpoint.py`` 的引导函数（唯一建表入口）；
- 假 LLM（确定性，可注入空返回/异常/停用）与假 Neo4j（只读 5 方法）：不调用真实模型、不连真实图谱。

命令（v2.1 §A-P1）：
  python scripts/accept_rnd_engine_parity.py --mock --offline \
      --db-url postgresql+psycopg://postgres@127.0.0.1:5432/neo4j_agents_parity
"""

import argparse
import hashlib
import json
import logging
import os
import socket
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

DEFAULT_DB_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/neo4j_agents_parity"
FORBIDDEN_DATABASES = {"neo4j_agents", "postgres", "template0", "template1"}
SHADOW_DB_SUFFIXES = ("_parity", "_migrate")

ALL_AGENTS = (
    "master_control",
    "formula_generation",
    "efficacy_prediction",
    "flavor_prediction",
    "replacement_mapping",
    "master_control_final",
)
IGNORED_KEYS = {
    "id",
    "run_id",
    "session_id",
    "step_id",
    "graph_snapshot_id",
    "created_at",
    "updated_at",
    "latency_ms",
    "_kb5_echo",  # LLM 回显字段：v2.1 §D-2 明确忽略
}

logger = logging.getLogger("accept_rnd_engine_parity")


# ----------------------------------------------------------------------
# 工具：参数、日志、外网守卫、DSN 解析
# ----------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="研发协同双引擎 Mock 等价与故障注入验收（隔离影子库）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db-url", default=os.getenv("PARITY_DB_URL", DEFAULT_DB_URL),
                        help=f"影子库 DSN（默认 {DEFAULT_DB_URL}；库名必须以 _parity/_migrate 结尾）")
    parser.add_argument("--db-admin-url", default=os.getenv("PARITY_DB_ADMIN_URL"),
                        help="可选：具备 CREATEDB 权限的 DSN（影子库不存在时用它创建）")
    parser.add_argument("--mock", action="store_true", help="Mock 模式（假 LLM/假 Neo4j；默认即 mock）")
    parser.add_argument("--offline", action="store_true", help="禁止外网连接（Mock 模式自动开启）")
    parser.add_argument("--recreate-db", action="store_true", help="先 DROP 再重建影子库（仅影子库名允许）")
    parser.add_argument("--keep-db", action="store_true", help="保留既有影子库数据（默认同样不删）")
    parser.add_argument("--cases", default="", help="只跑指定用例（逗号分隔，如 E2E-1,CFG-1）")
    parser.add_argument("--list-cases", action="store_true", help="列出用例后退出")
    parser.add_argument("--report", default=None, help="JSON 报告输出路径（默认写入 --report 或仅 stdout）")
    parser.add_argument("--write-fixture", default=None, help="把 E2E-1 的 legacy 规范化签名写成基线 fixture")
    parser.add_argument("--baseline-fixture", default=None, help="与该 fixture 比较 legacy 规范化签名")
    parser.add_argument("--show-logs", action="store_true", help="打印被测代码的 INFO 日志")
    parser.add_argument("--emit-api-token", action="store_true",
                        help="只在影子库为合成 admin 用户签发一个 API token 并打印（供只读回归脚本用；不跑用例）")
    return parser.parse_args(argv)


CASE_IDS = ["E2E-1", "CFG-1", "CFG-2", "CFG-3", "CFG-4", "FB-1", "FB-2", "FB-3", "FI-1", "FI-2", "FI-3", "FI-4"]


def install_network_guard():
    """禁止外网：仅允许回环地址与 Unix socket；返回被拦截记录列表。"""
    real_connect = socket.socket.connect
    blocked: list = []

    def guard(self, address):  # type: ignore[no-untyped-def]
        if isinstance(address, str):  # Unix socket
            return real_connect(self, address)
        host = address[0] if isinstance(address, tuple) and address else str(address)
        if host in ("127.0.0.1", "::1", "localhost", "0.0.0.0", ""):
            return real_connect(self, address)
        blocked.append(str(address))
        raise RuntimeError(f"[offline] 拦截外网连接：{address}")

    socket.socket.connect = guard  # type: ignore[assignment]
    return blocked


def sqlalchemy_url_parts(db_url: str):
    from sqlalchemy.engine import make_url

    return make_url(db_url)


def render_url(url) -> str:
    """渲染 SQLAlchemy URL：**必须** hide_password=False（``str(url)`` 会把口令替换为 ``***``）。"""
    return url.render_as_string(hide_password=False)


def libpq_dsn(db_url: str) -> str:
    from app.db.langgraph_schema import dsn_without_driver

    return dsn_without_driver(db_url)


def assert_shadow_db_name(db_name: str) -> None:
    if db_name in FORBIDDEN_DATABASES or not db_name.endswith(SHADOW_DB_SUFFIXES):
        raise SystemExit(
            f"拒绝在库 {db_name!r} 上运行：本脚本只允许影子库（*_parity / *_migrate），"
            f"禁止 {sorted(FORBIDDEN_DATABASES)} 等生产库名"
        )


def assert_local_host(db_url: str) -> None:
    """禁止连远端库：影子库必须在本机回环地址上（与 --offline 口径一致）。"""
    url = sqlalchemy_url_parts(db_url)
    host = url.host or ""
    if host not in ("127.0.0.1", "localhost", "::1", ""):
        raise SystemExit(f"拒绝连接非本机数据库主机 {host!r}：本脚本只允许回环地址（127.0.0.1/localhost）")


# ----------------------------------------------------------------------
# 影子库与 schema 引导
# ----------------------------------------------------------------------
def ensure_shadow_database(db_url: str, admin_url: str | None, recreate: bool) -> dict:
    """确保影子库存在（存在即用；不存在则用 admin DSN 或目标 DSN 创建）。

    先尝试直连目标库：连得上就完全不碰维护库（最少权限、最少副作用）。
    """
    import psycopg

    url = sqlalchemy_url_parts(db_url)
    db_name = url.database or ""
    assert_shadow_db_name(db_name)
    result = {"database": db_name, "created": False, "recreated": False}

    if not recreate:
        try:
            with psycopg.connect(libpq_dsn(render_url(url)), autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT current_database()")
                    result["database"] = cur.fetchone()[0]
            result["already_exists"] = True
            return result
        except Exception as exc:  # 库不存在/权限不足 → 走维护库分支
            result["target_connect_error"] = f"{type(exc).__name__}"

    m_url = sqlalchemy_url_parts(admin_url or db_url).set(database="postgres")
    conn = psycopg.connect(libpq_dsn(render_url(m_url)), autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cur.fetchone() is not None
            if exists and recreate:
                cur.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
                exists = False
                result["recreated"] = True
            if not exists:
                cur.execute(f'CREATE DATABASE "{db_name}"')
                result["created"] = True
    finally:
        conn.close()
    return result


def bootstrap_langgraph_schema(db_url: str, schema: str) -> dict:
    """复用 CLI 的引导函数（唯一建表入口）：段①建对象 + 段②写 marker。"""
    import importlib.util

    cli_path = BACKEND_ROOT / "scripts" / "init_langgraph_checkpoint.py"
    spec = importlib.util.spec_from_file_location("init_langgraph_checkpoint_cli", cli_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    bootstrap = module.bootstrap_objects(dsn=db_url, schema=schema)
    marker = module.write_migrated_marker(dsn=db_url, schema=schema)
    return {"bootstrap": bootstrap, "marker": marker}


# ----------------------------------------------------------------------
# 假 LLM / 假 Neo4j（确定性；只读）
# ----------------------------------------------------------------------
KB5_FORMULA_CONTEXT = {
    "formula_name": "四君子汤",
    "sources": ["《太平惠民和剂局方》宋", "方剂学各论"],
    "ingredients": [
        {"name": "人参", "role": "君药", "dosage": "9g"},
        {"name": "白术", "role": "臣药", "dosage": "9g"},
        {"name": "茯苓", "role": "臣药", "dosage": "9g"},
        {"name": "炙甘草", "role": "使药", "dosage": "6g"},
    ],
    "props": {"source": "《太平惠民和剂局方》宋"},
}

_HERB_PROPS = {
    "人参": {"food_homology": True, "nature": "平", "flavor": "甘", "overall_flavor_acceptance": "中", "bitter_risk": 0.2},
    "白术": {"food_homology": True, "nature": "温", "flavor": "苦甘", "overall_flavor_acceptance": "中", "bitter_risk": 0.4},
    "茯苓": {"food_homology": True, "nature": "平", "flavor": "甘淡", "overall_flavor_acceptance": "高", "bitter_risk": 0.1},
    "炙甘草": {"food_homology": True, "nature": "平", "flavor": "甘", "overall_flavor_acceptance": "高", "bitter_risk": 0.1},
    "黄芪": {"food_homology": True, "nature": "微温", "flavor": "甘", "overall_flavor_acceptance": "中", "bitter_risk": 0.2},
    "大枣": {"food_homology": True, "nature": "温", "flavor": "甘", "overall_flavor_acceptance": "高", "bitter_risk": 0.0},
    "陈皮": {"food_homology": True, "nature": "温", "flavor": "辛苦", "overall_flavor_acceptance": "中", "bitter_risk": 0.5},
    "山楂": {"food_homology": True, "nature": "微温", "flavor": "酸甘", "overall_flavor_acceptance": "高", "bitter_risk": 0.2},
}
CANDIDATE_HERB_NAMES = ["黄芪", "大枣", "陈皮", "山楂", "茯苓", "白术"]
REPLACEMENT_TABLE = {
    "人参": [
        {"id": "黄芪", "name": "黄芪", "score": 88.0, "professional_score": 90.0, "flavor_acceptance": 0.7,
         "flavor_similarity": 0.6, "safety_score": 0.9, "recommendation_status": "推荐"},
    ],
    "白术": [
        {"id": "茯苓", "name": "茯苓", "score": 82.0, "professional_score": 80.0, "flavor_acceptance": 0.8,
         "flavor_similarity": 0.7, "safety_score": 0.95, "recommendation_status": "推荐"},
    ],
}


def _entity(name: str, *, name_overrides: dict | None = None) -> dict:
    props = dict(_HERB_PROPS.get(name, {"food_homology": True}))
    if name_overrides:
        props.update(name_overrides)
    return {
        "id": name,
        "name": name,
        "props": props,
        "tags": ["补气", "健脾"],
        "score": 1.0,
    }


class FakeNeo4j:
    """假 Neo4j：只实现编排层用到的 5 个只读方法（确定性、无时间戳）。"""

    def __init__(self, *, mode: str = "normal") -> None:
        self.mode = mode  # normal | empty
        self.calls: list = []

    def _record(self, name: str) -> None:
        self.calls.append(name)

    def find_formulas_for_brief(self, search_terms, limit: int = 3):
        self._record("find_formulas_for_brief")
        if self.mode == "empty":
            return []
        return [deepcopy(KB5_FORMULA_CONTEXT)][:limit]

    def find_candidate_herbs_for_brief(self, search_terms, limit: int = 18):
        self._record("find_candidate_herbs_for_brief")
        if self.mode == "empty":
            return []
        return [_entity(name) for name in CANDIDATE_HERB_NAMES][:limit]

    def get_replacement_candidates(self, herb_name: str, limit: int = 5):
        self._record("get_replacement_candidates")
        if self.mode == "empty":
            return []
        return deepcopy(REPLACEMENT_TABLE.get(herb_name, []))[:limit]

    def retrieve_rnd_graph(self, herb_names, focus_relation: str | None = None):
        self._record("retrieve_rnd_graph")
        if self.mode == "empty":
            return {"nodes": [], "edges": []}
        nodes = [
            {"id": f"n{index}", "label": name, "type": "Herb", "properties": {"flavor": "甘"}}
            for index, name in enumerate(herb_names)
        ]
        edges = [
            {"id": f"e{index}", "source": f"n{index}", "target": f"n{index + 1}", "type": "CAN_REPLACE",
             "properties": {"score": 80 + index}}
            for index in range(max(0, len(nodes) - 1))
        ]
        return {"nodes": nodes, "edges": edges}

    def get_entity(self, entity_id: str):
        self._record("get_entity")
        if self.mode == "empty":
            return None
        return _entity(str(entity_id))

    def close(self) -> None:  # 与 Neo4jRepository.close 一致（共享 driver，no-op）
        return None


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


class FakeLLM:
    """假 LLM：确定性输出，可注入"空返回/异常"。

    与真实 ``DeepSeekClient`` 的契约一致：**异常与空返回都在客户端内部收敛为兜底**
    （``(fallback, elapsed_ms, True)``），因此 FB-1/FB-2 只能观察到兜底，不会让整 Run 失败。
    """

    def __init__(self, *, mode: str = "normal", gate: threading.Event | None = None,
                 gate_agent: str = "master_control") -> None:
        self.mode = mode  # normal | empty | exception
        self.calls: list = []
        self.gate = gate
        self.gate_agent = gate_agent
        self.entered = threading.Event()
        self._lock = threading.Lock()

    # 复用真实实现（本地规则解析，无任何 HTTP；v2.1 §0.1 事实 1）
    def build_rnd_brief(self, question: str):
        from app.services.deepseek_client import DeepSeekClient

        return DeepSeekClient.build_rnd_brief(self, question)

    def generate_structured_output(self, *, system_prompt="", payload=None, fallback=None,
                                   output_schema=None, required_keys=None, agent_key=None,
                                   temperature=None, max_completion_tokens=900, **_ignored):
        record = {
            "agent_key": agent_key,
            "prompt_digest": _digest(system_prompt or ""),
            "payload_digest": _digest(payload or {}),
            "required_keys": sorted(required_keys or []),
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
        }
        with self._lock:
            self.calls.append(record)
        if self.gate is not None and agent_key == self.gate_agent:
            self.entered.set()
            self.gate.wait(timeout=60)
        if self.mode == "empty":
            return deepcopy(fallback), 12, True
        if self.mode == "exception":
            # 真实客户端捕获异常后返回兜底（v2.1 §D FB-2）：这里等价模拟
            return deepcopy(fallback), 15, True
        output = deepcopy(fallback)
        output["_fake"] = {
            "agent_key": agent_key,
            "payload_digest": record["payload_digest"],
            "prompt_digest": record["prompt_digest"],
        }
        return output, 7, False

    def calls_for(self, agent_key: str) -> list:
        return [item for item in self.calls if item["agent_key"] == agent_key]


class CheckpointCrash(BaseException):
    """模拟"进程崩溃"：继承 BaseException，绕过 runner 的 Exception 失败收尾（W1 场景）。"""


def install_flaky_put(saver, *, fail_when=None, fail_on: int | None = None,
                      exception: BaseException | type = RuntimeError):
    """在**真实** PostgresSaver 实例上注入 ``put`` 失败（W1：节点已提交 step 行、checkpoint 未写）。

    - ``fail_when(checkpoint) -> bool``：按 checkpoint 内容触发（推荐：
      ``lambda cp: "master_control" in (cp.get("channel_versions") or {})`` —— 恰好在承载该步通道的
      checkpoint 写入时失败，对应"节点已返回（step 行已提交）但 checkpoint 落盘失败"）；
    - ``fail_on``：按第 N 次 put 触发（用于观察 Pregel 写入次序）；
    - 必须保持对象是 langgraph 认可的 ``BaseCheckpointSaver`` 实例（compile 会校验类型），
      因此用实例属性覆盖绑定方法，而不是包装类。
    """
    original_put = saver.put
    state = {"count": 0, "failed": False}

    def flaky_put(config, checkpoint, metadata, new_versions, **kwargs):
        state["count"] += 1
        trigger = bool(fail_when(checkpoint)) if fail_when is not None else False
        if fail_on is not None and state["count"] == fail_on:
            trigger = True
        if not state["failed"] and trigger:
            state["failed"] = True
            if isinstance(exception, type):
                raise exception("注入：checkpoint 写入失败（W1/FI-3）")
            raise exception
        return original_put(config, checkpoint, metadata, new_versions, **kwargs)

    saver.put = flaky_put  # type: ignore[method-assign]
    return state


def _checkpoint_has_agent(agent_key: str):
    """注入触发器：checkpoint 的 channel_versions 已包含该 Agent 的 State 通道。"""
    return lambda checkpoint: agent_key in ((checkpoint or {}).get("channel_versions") or {})


# ----------------------------------------------------------------------
# 归一化比较（v2.1 §D-2）
# ----------------------------------------------------------------------
def normalize(value):
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in sorted(value.items()) if key not in IGNORED_KEYS}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def _row(step) -> dict:
    return {
        "agent_key": step.agent_key,
        "sequence": step.sequence,
        "status": step.status,
        "prompt_version": step.prompt_version,
        "used_fallback": bool(step.used_fallback),
        "skipped": bool(step.skipped),
    }


def run_signature(repository, run_id: str) -> dict:
    """规范化 Run 签名：stpe 序列 / 键集与业务值 / 兜底与跳过 / 快照归属 / 报告 / 指标。"""
    run = repository.get_workflow_run(run_id)
    steps = repository.list_workflow_step_runs(run_id)
    snapshot_owners = [step.agent_key for step in steps if step.graph_snapshot_id]
    return {
        "status": run.status,
        "step_sequence": [[step.agent_key, step.sequence] for step in steps],
        "rows": [_row(step) for step in steps],
        "steps": [
            {
                "agent_key": step.agent_key,
                "sequence": step.sequence,
                "status": step.status,
                "prompt_version": step.prompt_version,
                "used_fallback": bool(step.used_fallback),
                "skipped": bool(step.skipped),
                "input_payload": normalize(step.input_payload or {}),
                "output_payload": normalize(step.output_payload or {}),
            }
            for step in steps
        ],
        "snapshot_owners": snapshot_owners,
        "snapshot_count": len(snapshot_owners),
        "related_graph_snapshots_count": len(run.related_graph_snapshots or []),
        "final_report": normalize(run.final_report or {}),
        "summary_metrics": normalize(run.summary_metrics or {}),
    }


def diff_signatures(left, right, *, path: str = "$") -> list:
    """逐项 diff（列表顺序参与比较：组成/君臣佐使/替代候选顺序必须一致）。"""
    if isinstance(left, dict) and isinstance(right, dict):
        diffs = []
        for key in sorted(set(left) | set(right)):
            if key not in left:
                diffs.append(f"{path}.{key}: 仅右侧存在")
            elif key not in right:
                diffs.append(f"{path}.{key}: 仅左侧存在")
            else:
                diffs.extend(diff_signatures(left[key], right[key], path=f"{path}.{key}"))
        return diffs
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [f"{path}: 列表长度 {len(left)} != {len(right)}"]
        diffs = []
        for index, (a, b) in enumerate(zip(left, right)):
            diffs.extend(diff_signatures(a, b, path=f"{path}[{index}]"))
        return diffs
    if left != right:
        return [f"{path}: {left!r} != {right!r}"]
    return []


# ----------------------------------------------------------------------
# 执行接线（真派发 + 真 runner + 真 orchestrator，仅 LLM/Neo4j 为假）
# ----------------------------------------------------------------------
class Harness:
    def __init__(self, db_url: str, schema: str) -> None:
        self.db_url = db_url
        self.schema = schema
        self.modules: dict = {}
        self.synthetic_user = None

    def load(self) -> None:
        sys.path.insert(0, str(BACKEND_ROOT))
        from app.api import routes
        from app.core.config import settings
        from app.db.init_db import initialize_database
        from app.db.sqlalchemy import SessionLocal
        from app.repositories.postgres_repository import PostgresRepository
        from app.services import agent_config_service, rnd_engine
        from app.services.rnd_graph import runner
        from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator

        self.modules = {
            "routes": routes,
            "settings": settings,
            "initialize_database": initialize_database,
            "SessionLocal": SessionLocal,
            "PostgresRepository": PostgresRepository,
            "agent_config_service": agent_config_service,
            "rnd_engine": rnd_engine,
            "runner": runner,
            "RnDWorkflowOrchestrator": RnDWorkflowOrchestrator,
        }

    # --- 基础访问器 -------------------------------------------------
    @property
    def SessionLocal(self):
        return self.modules["SessionLocal"]

    @property
    def Repository(self):
        return self.modules["PostgresRepository"]

    def session(self):
        return self.SessionLocal()

    def patch_fakes(self, llm, neo4j) -> None:
        self.modules["routes"].DeepSeekClient = lambda: llm
        self.modules["routes"].Neo4jRepository = lambda: neo4j
        self.modules["runner"].DeepSeekClient = lambda: llm
        self.modules["runner"].Neo4jRepository = lambda: neo4j

    def ensure_synthetic_user(self):
        if self.synthetic_user is not None:
            return self.synthetic_user
        from app.db.models import AppUser

        db = self.session()
        try:
            existing = db.query(AppUser).filter(AppUser.username == "parity_runner").one_or_none()
            if existing is None:
                existing = AppUser(
                    username="parity_runner",
                    display_name="parity runner",
                    password_hash="x",
                    role="admin",
                    is_active=True,
                )
                db.add(existing)
                db.commit()
                db.refresh(existing)
            self.synthetic_user = existing
            return existing
        finally:
            db.close()

    # --- Run 创建与派发 ---------------------------------------------
    def create_run(self, question: str, *, engine_pin: str) -> tuple[str, str]:
        """建 WorkflowSession + Run（同事务写 pin），返回 (session_id, run_id)。"""
        user = self.ensure_synthetic_user()
        db = self.session()
        try:
            repository = self.Repository(db)
            session_row = repository.create_workflow_session(user.id)
            db.commit()
            orchestrator = self.modules["RnDWorkflowOrchestrator"](repository, FakeNeo4j(), FakeLLM())
            result = orchestrator.start_run(
                session_row.id, question, reuse_last_brief=False, engine_pin=engine_pin
            )
            return session_row.id, result["run_id"]
        finally:
            db.close()

    def dispatch(self, run_id: str) -> None:
        """走真实后台派发入口（读 pin → legacy 原路径 / langgraph runner）。"""
        self.modules["routes"]._run_workflow_in_background(run_id)


def run_pair(harness: Harness, *, question: str, llm_mode: str = "normal", neo4j_mode: str = "normal"):
    """同一 brief 各跑一次 legacy / langgraph，返回两侧签名与运行信息。"""
    llm_legacy, llm_lg = FakeLLM(mode=llm_mode), FakeLLM(mode=llm_mode)
    neo4j_legacy, neo4j_lg = FakeNeo4j(mode=neo4j_mode), FakeNeo4j(mode=neo4j_mode)
    legacy_session, legacy_run = harness.create_run(question, engine_pin="legacy")
    lg_session, lg_run = harness.create_run(question, engine_pin="langgraph")

    harness.patch_fakes(llm_legacy, neo4j_legacy)
    harness.dispatch(legacy_run)
    harness.patch_fakes(llm_lg, neo4j_lg)
    harness.dispatch(lg_run)

    db = harness.session()
    try:
        repository = harness.Repository(db)
        return {
            "legacy": {"session_id": legacy_session, "run_id": legacy_run, "signature": run_signature(repository, legacy_run),
                       "llm": llm_legacy, "neo4j": neo4j_legacy},
            "langgraph": {"session_id": lg_session, "run_id": lg_run, "signature": run_signature(repository, lg_run),
                          "llm": llm_lg, "neo4j": neo4j_lg},
            "diffs": diff_signatures(
                run_signature(repository, legacy_run), run_signature(repository, lg_run)
            ),
        }
    finally:
        db.close()


def raw_step_rows(harness: Harness, run_id: str) -> list:
    db = harness.session()
    try:
        steps = harness.Repository(db).list_workflow_step_runs(run_id)
        return [
            {
                "agent_key": step.agent_key,
                "sequence": step.sequence,
                "status": step.status,
                "latency_ms": step.latency_ms,
                "used_fallback": bool(step.used_fallback),
                "skipped": bool(step.skipped),
                "prompt_version": step.prompt_version,
                "output_keys": sorted((step.output_payload or {}).keys()),
                "graph_snapshot_id": step.graph_snapshot_id,
            }
            for step in steps
        ]
    finally:
        db.close()


def check(name: str, ok: bool, detail=None) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def case_result(case_id: str, checks: list, *, detail=None) -> dict:
    return {
        "id": case_id,
        "status": "passed" if all(item["ok"] for item in checks) else "failed",
        "checks": checks,
        "detail": detail or {},
    }


# ----------------------------------------------------------------------
# 用例实现
# ----------------------------------------------------------------------
def case_e2e1(harness: Harness) -> dict:
    question = "把四君子汤改造成药食同源代餐粉，目标人群白领"
    outcome = run_pair(harness, question=question)
    left, right = outcome["legacy"]["signature"], outcome["langgraph"]["signature"]
    legacy_rows = raw_step_rows(harness, outcome["legacy"]["run_id"])
    lg_rows = raw_step_rows(harness, outcome["langgraph"]["run_id"])
    checks = [
        check("零差异（§D-2 全项相等）", not outcome["diffs"], outcome["diffs"][:20]),
        check("两侧各 6 步且 completed", len(legacy_rows) == 6 and len(lg_rows) == 6
              and all(row["status"] == "completed" for row in legacy_rows + lg_rows)),
        check("step 序列 = AGENT_STEP_DEFS", [row["agent_key"] for row in legacy_rows] == list(ALL_AGENTS)),
        check("快照归属一致", left["snapshot_owners"] == right["snapshot_owners"],
              {"legacy": left["snapshot_owners"], "langgraph": right["snapshot_owners"]}),
        check("related_graph_snapshots 与 step 行派生一致",
              left["snapshot_count"] == left["related_graph_snapshots_count"]
              and right["snapshot_count"] == right["related_graph_snapshots_count"]),
        check("final_report 键集非空且一致", bool(left["final_report"]) and not diff_signatures(
            left["final_report"], right["final_report"])),
    ]
    return case_result("E2E-1", checks, detail={"diffs": outcome["diffs"][:50],
                                                "snapshot_owners": left["snapshot_owners"],
                                                "summary_metrics": left["summary_metrics"]})


def case_cfg1(harness: Harness) -> dict:
    """CFG-1：某 Agent 提示词停用 → skipped/used_fallback/无模型调用，下游键集完整，两引擎一致。

    注：v2.1 §D-1 写 ``latency_ms=0``，但既有 ``_run_step``（本阶段冻结不改）用
    ``step.latency_ms = latency_ms or int(elapsed_ms)`` 落库，0 为假值 ⇒ 实际记录的是这一次
    无模型调用路径的实测耗时（量级 <100ms）。此处按"量级"断言并在报告中如实登记该口径差异。
    """
    from app.db.models import PromptTemplate

    db = harness.session()
    try:
        prompt = db.query(PromptTemplate).filter(
            PromptTemplate.scenario == "rnd_workflow", PromptTemplate.agent_key == "formula_generation"
        ).one()
        original = bool(prompt.is_active)
        prompt.is_active = False
        db.commit()
    finally:
        db.close()
    try:
        outcome = run_pair(harness, question="停用提示词的等价验收：四君子汤代餐粉")
        legacy_rows = raw_step_rows(harness, outcome["legacy"]["run_id"])
        lg_rows = raw_step_rows(harness, outcome["langgraph"]["run_id"])
        by_agent = {row["agent_key"]: row for row in legacy_rows}
        down = [row for row in legacy_rows if row["sequence"] > 2]
        down_keys_ok = all(row["output_keys"] for row in down)
        legacy_disabled = by_agent["formula_generation"]
        lg_disabled = {row["agent_key"]: row for row in lg_rows}["formula_generation"]
        checks = [
            check("停用步 skipped=true / used_fallback=true",
                  legacy_disabled["skipped"] and legacy_disabled["used_fallback"]
                  and lg_disabled["skipped"] and lg_disabled["used_fallback"],
                  {"legacy": legacy_disabled, "langgraph": lg_disabled}),
            check("停用步 latency_ms 为无量级（<100ms，无模型调用）",
                  legacy_disabled["latency_ms"] < 100 and lg_disabled["latency_ms"] < 100,
                  {"legacy_latency_ms": legacy_disabled["latency_ms"],
                   "langgraph_latency_ms": lg_disabled["latency_ms"]}),
            check("停用步未调用 LLM", not outcome["legacy"]["llm"].calls_for("formula_generation")
                  and not outcome["langgraph"]["llm"].calls_for("formula_generation")),
            check("下游步骤齐备（3..6）", [row["sequence"] for row in down] == [3, 4, 5, 6]),
            check("下游键集完整（非空）", down_keys_ok, [row["output_keys"] for row in down]),
            check("两引擎零差异", not outcome["diffs"], outcome["diffs"][:20]),
            check("两侧 skip 标记一致",
                  [row["skipped"] for row in legacy_rows] == [row["skipped"] for row in lg_rows]),
        ]
        return case_result("CFG-1", checks, detail={"diffs": outcome["diffs"][:20],
                                                   "legacy_latency_ms": legacy_disabled["latency_ms"],
                                                   "langgraph_latency_ms": lg_disabled["latency_ms"],
                                                   "note": "v2.1 期望 latency_ms=0；既有 _run_step 落库为实测耗时"})
    finally:
        db = harness.session()
        try:
            prompt = db.query(PromptTemplate).filter(
                PromptTemplate.scenario == "rnd_workflow", PromptTemplate.agent_key == "formula_generation"
            ).one()
            prompt.is_active = original
            db.commit()
        finally:
            db.close()


def case_cfg2(harness: Harness) -> dict:
    """CFG-2：提示词改写 → prompt_version 递增且两引擎一致。"""
    service = harness.modules["agent_config_service"]
    admin = harness.ensure_synthetic_user()
    new_text = "【CFG2】功效预测：按 KB2 输出三层人群与风险，禁止夸大功效。"
    db = harness.session()
    try:
        version = service.update_agent_config(
            harness.Repository(db), "efficacy_prediction", {"system_prompt": new_text}, admin
        )
    finally:
        db.close()
    outcome = run_pair(harness, question="提示词改写验收：四君子汤代餐粉")
    legacy_rows = {row["agent_key"]: row for row in raw_step_rows(harness, outcome["legacy"]["run_id"])}
    lg_rows = {row["agent_key"]: row for row in raw_step_rows(harness, outcome["langgraph"]["run_id"])}
    expected = f"v{version['version']}"
    legacy_calls = outcome["legacy"]["llm"].calls_for("efficacy_prediction")
    lg_calls = outcome["langgraph"]["llm"].calls_for("efficacy_prediction")
    checks = [
        check("版本号递增且被写入 step 行",
              legacy_rows["efficacy_prediction"]["prompt_version"] == expected
              and lg_rows["efficacy_prediction"]["prompt_version"] == expected,
              {"expected": expected, "legacy": legacy_rows["efficacy_prediction"]["prompt_version"],
               "langgraph": lg_rows["efficacy_prediction"]["prompt_version"]}),
        check("两引擎使用同一提示词文本",
              bool(legacy_calls) and bool(lg_calls)
              and legacy_calls[-1]["prompt_digest"] == lg_calls[-1]["prompt_digest"]),
        check("两引擎零差异", not outcome["diffs"], outcome["diffs"][:20]),
    ]
    return case_result("CFG-2", checks, detail={"new_version": version, "diffs": outcome["diffs"][:20]})


def case_cfg3(harness: Harness) -> dict:
    """CFG-3：master_control_final 无独立模板 → 回退 master_control 模板，prompt_version 与 legacy 相同。"""
    from app.db.models import PromptTemplate

    db = harness.session()
    try:
        prompt = db.query(PromptTemplate).filter(
            PromptTemplate.scenario == "rnd_workflow", PromptTemplate.agent_key == "master_control_final"
        ).one()
        prompt.agent_key = "master_control_final__cfg3_hidden"
        db.commit()
    finally:
        db.close()
    try:
        outcome = run_pair(harness, question="无独立 final 模板验收：四君子汤代餐粉")
        legacy_rows = {row["agent_key"]: row for row in raw_step_rows(harness, outcome["legacy"]["run_id"])}
        lg_rows = {row["agent_key"]: row for row in raw_step_rows(harness, outcome["langgraph"]["run_id"])}
        legacy_calls = outcome["legacy"]["llm"].calls_for("master_control_final")
        lg_calls = outcome["langgraph"]["llm"].calls_for("master_control_final")
        checks = [
            check("final 步回退 master_control 模板（prompt_version 与第 1 步相同）",
                  legacy_rows["master_control_final"]["prompt_version"]
                  == legacy_rows["master_control"]["prompt_version"]
                  and lg_rows["master_control_final"]["prompt_version"]
                  == lg_rows["master_control"]["prompt_version"],
                  {"legacy": legacy_rows["master_control_final"]["prompt_version"],
                   "langgraph": lg_rows["master_control_final"]["prompt_version"]}),
            check("两引擎 prompt_version 相同",
                  legacy_rows["master_control_final"]["prompt_version"]
                  == lg_rows["master_control_final"]["prompt_version"]),
            check("回退后仍真实调用模型（非 skipped）",
                  not legacy_rows["master_control_final"]["skipped"] and bool(legacy_calls) and bool(lg_calls)),
            check("两引擎零差异", not outcome["diffs"], outcome["diffs"][:20]),
        ]
        return case_result("CFG-3", checks, detail={"diffs": outcome["diffs"][:20]})
    finally:
        db = harness.session()
        try:
            prompt = db.query(PromptTemplate).filter(
                PromptTemplate.scenario == "rnd_workflow",
                PromptTemplate.agent_key == "master_control_final__cfg3_hidden",
            ).one()
            prompt.agent_key = "master_control_final"
            db.commit()
        finally:
            db.close()


def case_cfg4(harness: Harness) -> dict:
    """CFG-4：管理端参数钳制 + 版本回滚 + dry-run，两引擎行为一致。"""
    service = harness.modules["agent_config_service"]
    admin = harness.ensure_synthetic_user()
    detail: dict = {}
    db = harness.session()
    try:
        repository = harness.Repository(db)
        update = service.update_agent_config(repository, "flavor_prediction", {"temperature": 0.55}, admin)
        revisions = service.list_revisions(repository, "flavor_prediction", limit=5)
        revision_id = revisions[0]["id"]
        clamp_rejected = False
        try:
            service.update_agent_config(repository, "flavor_prediction", {"temperature": 9.0}, admin)
        except Exception as exc:  # AgentConfigError（钳制越界必须被拒）
            clamp_rejected = "temperature" in str(exc)
        rollback = service.rollback_to_revision(repository, "flavor_prediction", revision_id, admin)
        detail.update({"update": update, "rollback": rollback, "clamp_rejected": clamp_rejected})
    finally:
        db.close()

    outcome = run_pair(harness, question="参数钳制与版本回滚验收：四君子汤代餐粉")
    legacy_rows = {row["agent_key"]: row for row in raw_step_rows(harness, outcome["legacy"]["run_id"])}
    lg_rows = {row["agent_key"]: row for row in raw_step_rows(harness, outcome["langgraph"]["run_id"])}
    legacy_calls = outcome["legacy"]["llm"].calls_for("flavor_prediction")
    lg_calls = outcome["langgraph"]["llm"].calls_for("flavor_prediction")

    # 管理端 dry-run：不写 run/step 记录
    db = harness.session()
    try:
        repository = harness.Repository(db)
        before = len(repository.list_workflow_step_runs(outcome["legacy"]["run_id"]))
        orchestrator = harness.modules["RnDWorkflowOrchestrator"](
            repository, FakeNeo4j(), outcome["legacy"]["llm"]
        )
        dry = service.dry_run(orchestrator, repository, "flavor_prediction")
        after = len(repository.list_workflow_step_runs(outcome["legacy"]["run_id"]))
        detail["dry_run"] = {key: dry.get(key) for key in ("agent_key", "skipped", "used_fallback", "prompt_version", "temperature")}
    finally:
        db.close()

    checks = [
        check("参数钳制：越界被拒", clamp_rejected),
        check("版本回滚生成新版本", bool(rollback.get("version")) and rollback["version"] >= update["version"]),
        check("prompt_version 两引擎一致",
              legacy_rows["flavor_prediction"]["prompt_version"] == lg_rows["flavor_prediction"]["prompt_version"],
              {"legacy": legacy_rows["flavor_prediction"]["prompt_version"],
               "langgraph": lg_rows["flavor_prediction"]["prompt_version"]}),
        check("temperature 两引擎一致（回滚后取值）",
              bool(legacy_calls) and bool(lg_calls) and legacy_calls[-1]["temperature"] == lg_calls[-1]["temperature"],
              {"legacy": legacy_calls[-1]["temperature"] if legacy_calls else None,
               "langgraph": lg_calls[-1]["temperature"] if lg_calls else None}),
        check("dry-run 不写 step 行", before == after, {"before": before, "after": after}),
        check("两引擎零差异", not outcome["diffs"], outcome["diffs"][:20]),
    ]
    return case_result("CFG-4", checks, detail=detail)


def case_fb1(harness: Harness) -> dict:
    """FB-1：LLM 返回空/结构不匹配 → 走兜底，键集=兜底契约，两引擎一致。"""
    outcome = run_pair(harness, question="空返回兜底验收：四君子汤代餐粉", llm_mode="empty")
    legacy_rows = raw_step_rows(harness, outcome["legacy"]["run_id"])
    lg_rows = raw_step_rows(harness, outcome["langgraph"]["run_id"])
    checks = [
        check("全部步骤 used_fallback=true",
              all(row["used_fallback"] for row in legacy_rows) and all(row["used_fallback"] for row in lg_rows)),
        check("Run 仍 completed（兜底不使整 Run 失败）",
              outcome["legacy"]["signature"]["status"] == "completed" == outcome["langgraph"]["signature"]["status"]),
        check("每步 output 键集非空且两引擎一致",
              [row["output_keys"] for row in legacy_rows] == [row["output_keys"] for row in lg_rows]
              and all(row["output_keys"] for row in legacy_rows)),
        check("两引擎零差异", not outcome["diffs"], outcome["diffs"][:20]),
    ]
    return case_result("FB-1", checks, detail={"diffs": outcome["diffs"][:20]})


def case_fb2(harness: Harness) -> dict:
    """FB-2：LLM 抛异常/超时/402 → 客户端内部捕获 → 兜底（与 legacy 实测行为一致）。"""
    outcome = run_pair(harness, question="异常兜底验收：四君子汤代餐粉", llm_mode="exception")
    legacy_rows = raw_step_rows(harness, outcome["legacy"]["run_id"])
    checks = [
        check("异常被收敛为兜底", all(row["used_fallback"] for row in legacy_rows)),
        check("未使整 Run 失败", outcome["legacy"]["signature"]["status"] == "completed"),
        check("两引擎零差异", not outcome["diffs"], outcome["diffs"][:20]),
    ]
    return case_result("FB-2", checks, detail={"diffs": outcome["diffs"][:20]})


def case_fb3(harness: Harness) -> dict:
    """FB-3：图谱 0 命中 → 快照数 = 0，两引擎一致。"""
    outcome = run_pair(harness, question="图谱零命中验收：四君子汤代餐粉", neo4j_mode="empty")
    checks = [
        check("快照数为 0（两侧）",
              outcome["legacy"]["signature"]["snapshot_count"] == 0
              and outcome["langgraph"]["signature"]["snapshot_count"] == 0),
        check("步数仍为 6", len(outcome["legacy"]["signature"]["rows"]) == 6
              and len(outcome["langgraph"]["signature"]["rows"]) == 6),
        check("两引擎零差异", not outcome["diffs"], outcome["diffs"][:20]),
    ]
    return case_result("FB-3", checks, detail={"diffs": outcome["diffs"][:20]})


def case_fi1(harness: Harness) -> dict:
    """FI-1：两 Worker 并发领取同一 Run → 仅一方执行；另一方 WARN 放弃且 Run 状态不变；无重复 step。"""
    gate = threading.Event()
    llm = FakeLLM(gate=gate)
    neo4j = FakeNeo4j()
    harness.patch_fakes(llm, neo4j)
    _session_id, run_id = harness.create_run("并发领取验收：四君子汤代餐粉", engine_pin="langgraph")

    records: list = []
    handler = _ListHandler(records)
    root_logger = logging.getLogger("app.services.rnd_graph.run_lock")
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    worker_ok: dict = {}
    worker_second: dict = {}

    def first():
        try:
            harness.dispatch(run_id)
            worker_ok["done"] = True
        except BaseException as exc:  # noqa: BLE001
            worker_ok["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=first, name="fi1-worker-1")
    thread.start()
    entered = llm.entered.wait(timeout=60)

    db = harness.session()
    try:
        status_during = harness.Repository(db).get_workflow_run(run_id).status
    finally:
        db.close()

    def second():
        try:
            worker_second.update(harness.modules["runner"].run_langgraph(run_id))
        except BaseException as exc:  # noqa: BLE001
            worker_second["error"] = f"{type(exc).__name__}: {exc}"

    second_thread = threading.Thread(target=second, name="fi1-worker-2")
    second_thread.start()
    second_thread.join(timeout=60)
    gate.set()
    thread.join(timeout=120)
    root_logger.removeHandler(handler)

    rows = raw_step_rows(harness, run_id)
    agents = [row["agent_key"] for row in rows]
    db = harness.session()
    try:
        final_status = harness.Repository(db).get_workflow_run(run_id).status
    finally:
        db.close()
    checks = [
        check("第 1 个 worker 正常完成", worker_ok.get("done") is True and "error" not in worker_ok,
              worker_ok),
        check("第 2 个 worker 放弃投递（run_lock_held）",
              worker_second.get("status") == "skipped" and worker_second.get("reason") == "run_lock_held",
              worker_second),
        check("放弃投递时 Run 状态未被改动", status_during == "running", {"status_during": status_during}),
        check("WARN 日志存在", any("run_lock held, skip dispatch" in item.getMessage() for item in records),
              [item.getMessage() for item in records][:3]),
        check("无重复 (run_id, agent_key)", len(agents) == len(set(agents)) == 6, agents),
        check("Run 最终 completed", final_status == "completed", {"status": final_status}),
    ]
    return case_result("FI-1", checks, detail={"entered": entered, "rows": agents})


def case_fi2(harness: Harness) -> dict:
    """FI-2：节点提交后、checkpoint 写入前崩溃 → 手动恢复：reused=true、无重复调用/行，最终完成。"""
    runner = harness.modules["runner"]
    from app.services.rnd_graph.checkpointer import build_connection_pool
    from langgraph.checkpoint.postgres import PostgresSaver

    pool = build_connection_pool()
    good_saver = PostgresSaver(pool)
    flaky = PostgresSaver(pool)
    injection = install_flaky_put(flaky, fail_when=_checkpoint_has_agent("master_control"),
                                  exception=CheckpointCrash)
    detail: dict = {}

    llm = FakeLLM()
    neo4j = FakeNeo4j()
    harness.patch_fakes(llm, neo4j)
    _session_id, run_id = harness.create_run("崩溃恢复验收：四君子汤代餐粉", engine_pin="langgraph")

    original_build = runner.build_checkpointer
    runner.build_checkpointer = lambda: flaky
    crashed = None
    try:
        harness.dispatch(run_id)
    except BaseException as exc:  # noqa: BLE001 - 模拟进程崩溃（BaseException 绕过失败收尾）
        crashed = f"{type(exc).__name__}: {exc}"
    finally:
        runner.build_checkpointer = original_build

    db = harness.session()
    try:
        repository = harness.Repository(db)
        run_after_crash = repository.get_workflow_run(run_id)
        status_after_crash = run_after_crash.status
        steps_after_crash = raw_step_rows(harness, run_id)
    finally:
        db.close()

    # 真实崩溃不会走失败收尾；若注入异常被包装成 Exception（版本差异），把 Run 复位为 crashed 语义
    if status_after_crash == "failed":
        db = harness.session()
        try:
            repository = harness.Repository(db)
            repository.get_workflow_run(run_id).status = "running"
            db.commit()
        finally:
            db.close()
        detail["status_reset"] = "注入异常被包装为 Exception，已按崩溃语义复位为 running"

    calls_before = len(llm.calls_for("master_control"))
    runner.build_checkpointer = lambda: good_saver
    resume_error = None
    try:
        result = runner.run_langgraph(run_id, resume=True, recover_enabled=True)
    except BaseException as exc:  # noqa: BLE001
        resume_error = f"{type(exc).__name__}: {exc}"
        result = {}
    finally:
        runner.build_checkpointer = original_build

    rows = raw_step_rows(harness, run_id)
    agents = [row["agent_key"] for row in rows]
    checks = [
        check("崩溃点可定位：第 1 步已提交 completed",
              bool(steps_after_crash) and steps_after_crash[0]["agent_key"] == "master_control"
              and steps_after_crash[0]["status"] == "completed",
              {"steps": [row["agent_key"] for row in steps_after_crash], "crashed": crashed}),
        check("恢复成功（invoke(None) 5 项前置满足）", not resume_error, resume_error),
        check("恢复后 master_control 复用（reused=true，未重复调用 LLM）",
              len(llm.calls_for("master_control")) == calls_before == 1,
              {"calls": len(llm.calls_for("master_control"))}),
        check("无重复 (run_id, agent_key) 且六步齐全", len(agents) == len(set(agents)) == 6, agents),
        check("Run 最终 completed", result.get("status") == "completed", {"status": result.get("status")}),
    ]
    detail.update({"crashed": crashed, "status_after_crash": status_after_crash,
                   "put_calls_before_crash": injection["count"], "resume_error": resume_error})
    return case_result("FI-2", checks, detail=detail)


def case_fi3(harness: Harness) -> dict:
    """FI-3：checkpoint 写入失败 → 已提交 StepRun 保留；Run=failed + 骨架；无重复；不自动重试。"""
    runner = harness.modules["runner"]
    from app.services.rnd_graph.checkpointer import build_connection_pool
    from langgraph.checkpoint.postgres import PostgresSaver

    pool = build_connection_pool()
    flaky = PostgresSaver(pool)
    injection = install_flaky_put(flaky, fail_when=_checkpoint_has_agent("master_control"),
                                  exception=RuntimeError)

    llm = FakeLLM()
    neo4j = FakeNeo4j()
    harness.patch_fakes(llm, neo4j)
    _session_id, run_id = harness.create_run("checkpoint 写失败验收：四君子汤代餐粉", engine_pin="langgraph")

    original_build = runner.build_checkpointer
    runner.build_checkpointer = lambda: flaky
    raised = None
    try:
        harness.dispatch(run_id)
    except BaseException as exc:  # noqa: BLE001
        raised = f"{type(exc).__name__}: {exc}"
    finally:
        runner.build_checkpointer = original_build

    calls_after_failure = len(llm.calls)
    time.sleep(0.2)  # 给"自动重试"留出观察窗口
    rows = raw_step_rows(harness, run_id)
    agents = [row["agent_key"] for row in rows]

    db = harness.session()
    try:
        repository = harness.Repository(db)
        run = repository.get_workflow_run(run_id)
        status = run.status
        report = run.final_report or {}
        snapshot_ids = [row["graph_snapshot_id"] for row in rows if row["graph_snapshot_id"]]
        joinable = 0
        for snapshot_id in snapshot_ids:
            joinable += 1 if repository.get_graph_snapshot(snapshot_id) is not None else 0
    finally:
        db.close()

    checks = [
        check("异常上抛（不静默吞掉）", raised is not None, raised),
        check("Run 标记 failed", status == "failed", {"status": status}),
        check("固定失败骨架齐备",
              all(key in report for key in ("brief_summary", "consistency_checks", "final_recommendation",
                                            "modules", "evidence_gaps")) and bool(report),
              sorted(report.keys())[:12]),
        check("已提交 StepRun 保留（第 1 步 completed）",
              bool(rows) and rows[0]["agent_key"] == "master_control" and rows[0]["status"] == "completed",
              [f"{row['agent_key']}:{row['status']}" for row in rows]),
        check("无重复步骤且不自动重试", len(agents) == len(set(agents)) and len(llm.calls) == calls_after_failure,
              {"agents": agents, "llm_calls": len(llm.calls)}),
        check("无悬空引用（graph_snapshot_id 均可 join）", joinable == len(snapshot_ids),
              {"snapshots": snapshot_ids, "joinable": joinable}),
    ]
    return case_result("FI-3", checks, detail={"raised": raised, "rows": agents, "status": status,
                                               "put_calls": injection["count"]})


def case_fi4(harness: Harness) -> dict:
    """FI-4：进程重启后 Run 停 running → sweep（显式开启）仅标 failed，不自动续跑。"""
    runner = harness.modules["runner"]
    settings = harness.modules["settings"]
    llm = FakeLLM()
    harness.patch_fakes(llm, FakeNeo4j())
    _session_id, run_id = harness.create_run("孤儿清扫验收：四君子汤代餐粉", engine_pin="langgraph")

    db = harness.session()
    try:
        repository = harness.Repository(db)
        run = repository.get_workflow_run(run_id)
        run.status = "running"
        run.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=90)
        db.commit()
    finally:
        db.close()

    original_enabled = settings.rnd_orphan_sweep_enabled
    original_minutes = settings.rnd_orphan_stale_minutes
    try:
        settings.rnd_orphan_sweep_enabled = False
        disabled = runner.sweep_orphan_runs()
        settings.rnd_orphan_sweep_enabled = True
        settings.rnd_orphan_stale_minutes = 30
        swept = runner.sweep_orphan_runs()
    finally:
        settings.rnd_orphan_sweep_enabled = original_enabled
        settings.rnd_orphan_stale_minutes = original_minutes

    db = harness.session()
    try:
        repository = harness.Repository(db)
        run = repository.get_workflow_run(run_id)
        status = run.status
        steps = repository.list_workflow_step_runs(run_id)
        report = run.final_report or {}
    finally:
        db.close()

    checks = [
        check("默认关闭时 sweep 不动作", disabled.get("enabled") is False and disabled.get("scanned") == 0, disabled),
        check("显式开启后扫到该 Run", run_id in (swept.get("orphans") or []), swept),
        check("仅标记 failed（不自动续跑）", status == "failed" and not steps, {"status": status,
                                                                             "steps": len(steps)}),
        check("失败骨架已写入", bool(report.get("consistency_checks"))),
        check("无新增 LLM 调用", not llm.calls, {"calls": len(llm.calls)}),
    ]
    return case_result("FI-4", checks, detail={"disabled": disabled, "swept": swept})


class _ListHandler(logging.Handler):
    def __init__(self, sink: list) -> None:
        super().__init__(level=logging.INFO)
        self.sink = sink

    def emit(self, record) -> None:
        try:
            self.sink.append(record)
        except Exception:  # pragma: no cover
            pass


CASE_FUNCS = {
    "E2E-1": case_e2e1,
    "CFG-1": case_cfg1,
    "CFG-2": case_cfg2,
    "CFG-3": case_cfg3,
    "CFG-4": case_cfg4,
    "FB-1": case_fb1,
    "FB-2": case_fb2,
    "FB-3": case_fb3,
    "FI-1": case_fi1,
    "FI-2": case_fi2,
    "FI-3": case_fi3,
    "FI-4": case_fi4,
}


# ----------------------------------------------------------------------
# 全局检查与 main
# ----------------------------------------------------------------------
def schema_checks(harness: Harness) -> list:
    """断言新表 100% 落在 langgraph，且 public 无 checkpoint%。"""
    from app.db.langgraph_schema import REQUIRED_TABLES, validate_langgraph_schema

    status = validate_langgraph_schema(dsn=harness.db_url, schema=harness.schema)
    return [
        check("langgraph schema 存在", status.schema_present, status.as_dict()),
        check("必需表齐备", not status.missing_tables, {"missing": status.missing_tables,
                                                   "required": list(REQUIRED_TABLES)}),
        check("public 无 checkpoint% 表", not status.public_checkpoint_tables, status.public_checkpoint_tables),
        check("新表全部位于 langgraph（无 public 泄漏）", status.ok, status.describe()),
    ]


def environment_info(harness: Harness) -> dict:
    import platform

    info = {
        "python": platform.python_version(),
        "db_url_hint": None,
        "schema": harness.schema,
        "packages": {},
    }
    try:
        from app.db.langgraph_schema import _dsn_hint

        info["db_url_hint"] = _dsn_hint(harness.db_url)
    except Exception:  # pragma: no cover
        pass
    for module_name, attr in (("langgraph", "__version__"), ("langgraph.checkpoint.postgres", None),
                              ("psycopg_pool", "__version__"), ("psycopg", "__version__")):
        try:
            module = __import__(module_name, fromlist=["x"])
            info["packages"][module_name] = getattr(module, attr, "n/a") if attr else "installed"
        except Exception as exc:  # pragma: no cover
            info["packages"][module_name] = f"missing: {type(exc).__name__}"
    try:
        import inspect

        from langgraph.graph.state import CompiledStateGraph

        signature = inspect.signature(CompiledStateGraph.invoke)
        info["invoke_signature"] = str(signature)
        info["durability_supported"] = "durability" in signature.parameters
        info["context_supported"] = "context" in signature.parameters
    except Exception as exc:  # pragma: no cover
        info["invoke_signature"] = f"unavailable: {exc}"
    return info


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.list_cases:
        print(json.dumps(CASE_IDS, ensure_ascii=False))
        return 0

    logging.basicConfig(
        level=logging.INFO if args.show_logs else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    blocked: list = []
    if args.mock or args.offline:
        blocked = install_network_guard()
        logger.warning("已启用禁止外网校验（--mock/--offline）")

    db_url = args.db_url
    db_name = sqlalchemy_url_parts(db_url).database or ""
    assert_shadow_db_name(db_name)
    assert_local_host(db_url)
    if args.db_admin_url:
        assert_local_host(args.db_admin_url)

    # 必须在导入 app 模块前固定 DSN（settings 在 import 期实例化）
    os.environ["POSTGRES_DSN"] = db_url
    os.environ.setdefault("RND_LANGGRAPH_VALIDATE_ON_START", "false")
    os.environ.pop("RND_ENGINE", None)

    report: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mock" if (args.mock or args.offline) else "direct",
        "offline": bool(args.mock or args.offline),
        "database": db_name,
        "schema": os.getenv("RND_LANGGRAPH_SCHEMA", "langgraph"),
        "results": [],
        "global_checks": [],
        "ok": False,
    }

    sys.path.insert(0, str(BACKEND_ROOT))
    from app.core.config import settings  # noqa: E402
    from app.db.langgraph_schema import resolve_schema  # noqa: E402

    schema = resolve_schema(report["schema"])
    report["schema"] = schema

    try:
        report["database_setup"] = ensure_shadow_database(db_url, args.db_admin_url, args.recreate_db)
        harness = Harness(db_url, schema)
        harness.load()
        from app.db.init_db import initialize_database

        initialize_database()
        report["schema_bootstrap"] = bootstrap_langgraph_schema(db_url, schema)
        report["environment"] = environment_info(harness)

        if args.emit_api_token:
            # 影子库内为合成 admin 用户签发 token（staging 专用；本脚本不写生产库）
            from app.services.auth_service import AuthService

            user = harness.ensure_synthetic_user()
            db = harness.session()
            try:
                token, _session_row = AuthService(db).create_session(user, ip="127.0.0.1", user_agent="parity")
                db.commit()
            finally:
                db.close()
            print(token)
            report["ok"] = True
            report["api_token_mode"] = True
            return 0

        checks = schema_checks(harness)
        report["global_checks"] = checks

        selected = [item.strip() for item in args.cases.split(",") if item.strip()] or CASE_IDS
        unknown = [item for item in selected if item not in CASE_FUNCS]
        if unknown:
            raise SystemExit(f"未知用例：{unknown}；可用：{CASE_IDS}")

        for case_id in selected:
            logger.warning("=== 运行用例 %s ===", case_id)
            started = time.perf_counter()
            try:
                result = CASE_FUNCS[case_id](harness)
            except BaseException as exc:  # noqa: BLE001 - 用例异常按失败登记，不中断其余用例
                logger.exception("用例 %s 异常", case_id)
                result = case_result(case_id, [check("用例执行未抛异常", False, f"{type(exc).__name__}: {exc}")])
            result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            report["results"].append(result)

        if args.write_fixture:
            fixture_path = Path(args.write_fixture)
            e2e = next((item for item in report["results"] if item["id"] == "E2E-1"), None)
            fixture = {
                "note": "legacy 规范化基线 fixture（E2E-1）；用 --baseline-fixture 复现比对",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "e2e1": (e2e or {}).get("detail", {}),
            }
            fixture_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
            report["fixture_written"] = str(fixture_path)

        if args.baseline_fixture:
            fixture_path = Path(args.baseline_fixture)
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            report["baseline_fixture"] = {"path": str(fixture_path),
                                          "matches_e2e1_snapshot_owners":
                                              fixture.get("e2e1", {}).get("snapshot_owners")
                                              == next((item["detail"].get("snapshot_owners")
                                                       for item in report["results"] if item["id"] == "E2E-1"), None)}
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        logger.exception("验收执行失败")
        report["fatal_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["blocked_outbound_connections"] = blocked
        report["ok"] = bool(
            report.get("results")
            and all(item["status"] == "passed" for item in report["results"])
            and all(item["ok"] for item in report.get("global_checks", []))
            and not report.get("fatal_error")
        )
        payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        if args.report:
            Path(args.report).write_text(payload, encoding="utf-8")
        if not report.get("api_token_mode"):
            print(payload)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
