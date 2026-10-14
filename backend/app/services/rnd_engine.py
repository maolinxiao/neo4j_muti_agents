"""双引擎开关：决策、pin 固定与缺 pin 判定（v2.1 §C.2/§C.5）。

决策优先级：``system_config.rnd_engine`` → 环境变量 ``RND_ENGINE`` → 默认 ``legacy``（TTL 15s 缓存）。

``system_config.rnd_engine`` 取值口径：
- 裸字符串：``legacy`` / ``langgraph``；
- JSON：``{"mode":"legacy"}`` / ``{"mode":"langgraph"}`` / ``{"mode":"canary","users":["<user_id>", ...]}``
  （canary 仅对白名单用户生效，其余用户仍 legacy）。

引擎固定（同事务）：``POST /api/rnd/sessions/{sid}/runs`` 先决策，再在 ``start_run`` 的**同一事务**里
写 ``langgraph.run_engine(run_id, engine, pinned_at)``；写 pin 失败 → 回滚 + 接口 503（不入队、不降级）。

缺 pin 判定（执行入口）：``created_at < rnd_engine_migrated_at`` → legacy；否则 Run 标记 ``failed``
并给出明确错误（**禁止静默降级**）。
"""

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.db.langgraph_schema import RUN_ENGINE_TABLE, resolve_schema
from app.repositories.postgres_repository import PostgresRepository

logger = logging.getLogger(__name__)


ENGINE_LEGACY = "legacy"
ENGINE_LANGGRAPH = "langgraph"
ENGINE_CHOICES = (ENGINE_LEGACY, ENGINE_LANGGRAPH)

ENGINE_CONFIG_KEY = "rnd_engine"
MIGRATED_AT_KEY = "rnd_engine_migrated_at"

#: 引擎固定失败时**对外**（HTTP 503）的通用文案：不含异常类名/relation/SQL/连接串等内部细节
#: （v2.1 §E.9 日志与对外错误脱敏口径；v2.2 §11 finding G5 修复）。
ENGINE_PIN_FAILURE_DETAIL = "研发任务引擎固定失败，请联系管理员（可能原因：LangGraph 存储未初始化）"
#: 执行期发现 Run 缺少/无法读取引擎 pin 时的**对外/入库**通用文案（内部原因只写服务端日志）。
ENGINE_UNPINNED_DETAIL = "研发任务引擎未正确固定，任务已标记失败，请联系管理员"


class EnginePinError(RuntimeError):
    """引擎 pin 写入失败（同事务内异常 → 回滚 + 503，不入队、不降级）。

    脱敏约定（§E.9）：
    - ``str(exc)`` 只为**通用文案 + 可追踪标识**：即使被上游 re-wrap（``except Exception`` → 新异常）
      也不会把内部细节带进对外响应；
    - ``internal_detail`` / ``stage`` / ``engine`` / ``run_id`` 供**服务端日志**排查用，不得进 HTTP 响应。
    """

    def __init__(
        self,
        message: str = "",
        *,
        run_id: str | None = None,
        engine: str | None = None,
        stage: str = "pin_write",
        internal_detail: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.engine = engine
        self.stage = stage
        self.internal_detail = internal_detail
        super().__init__(message or ENGINE_PIN_FAILURE_DETAIL)


def _exception_chain(exc: BaseException | None, *, max_depth: int = 6):
    """遍历异常链（``__cause__`` / ``__context__``），带环检测与深度上限。"""
    seen: set[int] = set()
    current = exc
    depth = 0
    while current is not None and depth < max_depth:
        if id(current) in seen:
            break
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__
        depth += 1


def _chain_attr(exc: BaseException | None, name: str) -> str | None:
    """从异常链取非空字符串属性（只读属性，不解析异常消息文本，避免夹带内部细节）。"""
    for item in _exception_chain(exc):
        value = getattr(item, name, None)
        if isinstance(value, str) and value:
            return value
    return None


def run_id_of(exc: BaseException | None) -> str | None:
    """从异常链取可追踪的 ``run_id``（用于对外 503 文案与服务端日志）。"""
    return _chain_attr(exc, "run_id")


def engine_of(exc: BaseException | None) -> str | None:
    """从异常链取引擎标识（仅用于服务端日志，属 §E.9 白名单字段）。"""
    return _chain_attr(exc, "engine")


def public_detail_for(exc: BaseException | None) -> str:
    """把引擎固定失败的异常链收敛为对外 503 文案：通用文案（+ run_id 这类白名单标识）。

    绝不回显：异常类名、PostgreSQL relation/表名、SQL 片段、psycopg 内部信息、堆栈或连接串。
    """
    run_id = run_id_of(exc)
    if run_id:
        return f"{ENGINE_PIN_FAILURE_DETAIL}（run_id={run_id}）"
    return ENGINE_PIN_FAILURE_DETAIL


_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"value": None, "source": None, "loaded_at": None}


def reset_cache() -> None:
    """清空引擎决策缓存（运维切换后立即生效、验收脚本用）。"""
    with _cache_lock:
        _cache.update({"value": None, "source": None, "loaded_at": None})


def _ttl_seconds() -> int:
    try:
        return max(0, int(settings.rnd_engine_cache_ttl_seconds))
    except (TypeError, ValueError):  # pragma: no cover
        return 15


def _cache_fresh() -> bool:
    loaded_at = _cache.get("loaded_at")
    if loaded_at is None or _cache.get("value") is None:
        return False
    age = (datetime.now(timezone.utc) - loaded_at).total_seconds()
    return age < _ttl_seconds()


def load_engine_config(*, session: Any = None) -> tuple[str | None, str]:
    """读取引擎配置原文与来源（``system_config`` → env → 默认）。

    返回 ``(raw_value, source)``；``raw_value`` 为 ``system_config`` 的值或环境变量值，None 表示未配置。
    """
    if _cache_fresh():
        return _cache["value"], _cache["source"]
    raw: str | None = None
    source = "default"
    own_session = None
    try:
        if session is None:
            from app.db.sqlalchemy import SessionLocal

            own_session = SessionLocal()
            session = own_session
        raw = PostgresRepository(session).get_system_config_value(ENGINE_CONFIG_KEY)
        if raw is not None and str(raw).strip() != "":
            source = "system_config"
        else:
            raw = None
    except Exception:
        logger.warning("读取 system_config.%s 失败，回退环境变量/默认值", ENGINE_CONFIG_KEY, exc_info=True)
        raw = None
    finally:
        if own_session is not None:
            try:
                own_session.close()
            except Exception:  # pragma: no cover
                pass

    if raw is None:
        env_value = (settings.rnd_engine or "").strip() or None
        if env_value:
            raw = env_value
            source = "env"

    with _cache_lock:
        _cache.update({"value": raw, "source": source, "loaded_at": datetime.now(timezone.utc)})
    return raw, source


def parse_engine_config(raw: str | None, user_id: str | None = None) -> str:
    """把配置原文解析为某用户实际生效的引擎（无法识别一律 legacy，并 WARN）。"""
    if raw is None:
        return ENGINE_LEGACY
    text_value = str(raw).strip()
    if not text_value:
        return ENGINE_LEGACY
    if text_value.startswith("{"):
        try:
            payload = json.loads(text_value)
        except (TypeError, ValueError):
            logger.warning("system_config.%s 非合法 JSON，按 legacy 处理", ENGINE_CONFIG_KEY)
            return ENGINE_LEGACY
        if not isinstance(payload, dict):
            logger.warning("system_config.%s JSON 不是对象，按 legacy 处理", ENGINE_CONFIG_KEY)
            return ENGINE_LEGACY
        mode = str(payload.get("mode") or "").strip().lower()
        if mode == ENGINE_LANGGRAPH:
            return ENGINE_LANGGRAPH
        if mode == "canary":
            users = payload.get("users") or []
            if isinstance(users, str):
                users = [item.strip() for item in users.split(",") if item.strip()]
            if user_id and str(user_id) in {str(item) for item in users}:
                return ENGINE_LANGGRAPH
            return ENGINE_LEGACY
        if mode in ("", ENGINE_LEGACY):
            return ENGINE_LEGACY
        logger.warning("system_config.%s mode=%s 不可识别，按 legacy 处理", ENGINE_CONFIG_KEY, mode)
        return ENGINE_LEGACY
    lowered = text_value.lower()
    if lowered in ENGINE_CHOICES:
        return lowered
    logger.warning("system_config.%s 取值 %s 不可识别，按 legacy 处理", ENGINE_CONFIG_KEY, text_value)
    return ENGINE_LEGACY


def decide(user_id: str | None = None, *, session: Any = None) -> str:
    """决策本次 Run 的引擎（默认 legacy）。"""
    raw, source = load_engine_config(session=session)
    engine = parse_engine_config(raw, user_id)
    logger.info("rnd_engine 决策 engine=%s source=%s user_id=%s", engine, source, user_id)
    return engine


# ----------------------------------------------------------------------
# pin 写入/读取（同事务）
# ----------------------------------------------------------------------
def write_run_engine(session: Any, run_id: str, engine: str, *, schema: str | None = None) -> None:
    """在调用方事务内写引擎 pin；异常上抛（调用方负责回滚 + 503）。

    使用普通 INSERT（无 ON CONFLICT）：同一 Run 重复写 pin 属异常情形，必须**响亮失败**而非静默覆盖。

    脱敏（§E.9）：内部原因写服务端日志（含 run_id/engine/stage 白名单字段与堆栈），
    对外抛出的 ``EnginePinError`` 只携带通用文案（见 ``public_detail_for``）。
    """
    try:
        if engine not in ENGINE_CHOICES:
            raise ValueError(f"非法引擎取值：{engine!r}")
        table = f"{resolve_schema(schema)}.{RUN_ENGINE_TABLE}"
        session.execute(
            text(f"INSERT INTO {table} (run_id, engine, pinned_at) VALUES (:run_id, :engine, now())"),
            {"run_id": run_id, "engine": engine},
        )
    except Exception as exc:
        # 服务端日志保留完整可排查信息（run_id/engine/stage/schema + 堆栈）；不进 HTTP 响应
        logger.error(
            "rnd_engine pin 写入失败 run_id=%s engine=%s stage=pin_write schema=%s",
            run_id,
            engine,
            settings.rnd_langgraph_schema,
            exc_info=True,
        )
        raise EnginePinError(
            ENGINE_PIN_FAILURE_DETAIL,
            run_id=run_id,
            engine=str(engine),
            stage="pin_write",
            internal_detail=f"{type(exc).__name__}: {exc}",
        ) from exc
    logger.info("rnd_engine pin 写入 run_id=%s engine=%s", run_id, engine)


def read_run_engine(session: Any, run_id: str, *, schema: str | None = None) -> str | None:
    """读取 Run 的引擎 pin（无行返回 None）。读取异常由调用方处置（失败不降级）。"""
    table = f"{resolve_schema(schema)}.{RUN_ENGINE_TABLE}"
    row = session.execute(
        text(f"SELECT engine FROM {table} WHERE run_id = :run_id"), {"run_id": run_id}
    ).fetchone()
    if row is None:
        return None
    value = row[0]
    return str(value) if value is not None else None


def read_migrated_at(*, session: Any = None) -> datetime | None:
    """读取 ``rnd_engine_migrated_at`` marker（naive UTC，便于与 ``created_at`` 比较）。

    缺失/不可解析 → None（调用方按"未迁移"处理，即历史 Run 视为 legacy）。
    """
    own_session = None
    value: str | None = None
    try:
        if session is None:
            from app.db.sqlalchemy import SessionLocal

            own_session = SessionLocal()
            session = own_session
        value = PostgresRepository(session).get_system_config_value(MIGRATED_AT_KEY)
    except Exception:
        logger.warning("读取 system_config.%s 失败（按未迁移处理）", MIGRATED_AT_KEY, exc_info=True)
        return None
    finally:
        if own_session is not None:
            try:
                own_session.close()
            except Exception:  # pragma: no cover
                pass
    return parse_marker_timestamp(value)


def parse_marker_timestamp(value: str | None) -> datetime | None:
    """把 marker 文本解析为 naive UTC datetime（PG ``now()::text`` 形如 ``2026-10-15 09:12:33.1+08``）。"""
    if not value:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    normalized = text_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        logger.warning("system_config.%s 值 %s 无法解析为时间，按未迁移处理", MIGRATED_AT_KEY, text_value)
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def resolve_engine_for_run(run_id: str) -> str:
    """执行入口的引擎分派：pin → 分派；无 pin → 按 marker 判定；无法判定 → 标记 failed 并抛错。

    - ``legacy``：原路径原样执行；
    - ``langgraph``：交给 ``rnd_graph.runner``；
    - 无 pin 且 ``created_at < rnd_engine_migrated_at``（或 marker 缺失）→ legacy（历史 Run）；
    - 无 pin 且已过 marker → Run 置 ``failed`` + 明确错误（不静默降级）。
    """
    from app.db.sqlalchemy import SessionLocal

    db = SessionLocal()
    try:
        run = PostgresRepository(db).get_workflow_run(run_id)
        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")
        created_at = run.created_at
        try:
            engine = read_run_engine(db, run_id)
        except Exception as exc:
            db.rollback()
            # 内部细节只进服务端日志；入库的失败骨架与抛出文案均为通用文案（§E.9）
            logger.exception("读取 langgraph.run_engine 失败 run_id=%s", run_id)
            _fail_run(run_id, RuntimeError(ENGINE_UNPINNED_DETAIL), "读取引擎 pin 失败（禁止静默降级）")
            raise RuntimeError(ENGINE_UNPINNED_DETAIL) from exc
        if engine in ENGINE_CHOICES:
            return engine
        if engine is not None:
            logger.warning("langgraph.run_engine 取值异常 run_id=%s engine=%s，按 failed 处理", run_id, engine)
            _fail_run(run_id, RuntimeError(ENGINE_UNPINNED_DETAIL), "引擎 pin 取值非法")
            raise RuntimeError(ENGINE_UNPINNED_DETAIL)
        marker = read_migrated_at(session=db)
        if marker is None or (created_at is not None and created_at < marker):
            logger.warning(
                "Run 无引擎 pin，按历史 Run（legacy）执行 run_id=%s created_at=%s marker=%s",
                run_id,
                created_at,
                marker,
            )
            return ENGINE_LEGACY
        # 迁移后缺 pin：原因只写日志（含 created_at/marker），对外与入库均为通用文案
        logger.error(
            "Run 缺少引擎 pin（created_at=%s >= rnd_engine_migrated_at=%s）：禁止静默降级，Run 标记 failed，run_id=%s",
            created_at,
            marker,
            run_id,
        )
        _fail_run(run_id, RuntimeError(ENGINE_UNPINNED_DETAIL), "缺少引擎 pin（迁移后）")
        raise RuntimeError(ENGINE_UNPINNED_DETAIL)
    finally:
        db.close()


def _fail_run(run_id: str, exc: BaseException, context: str) -> None:
    """标记 Run 失败（复用 runner 的失败收尾，延迟导入避免循环依赖）。"""
    from app.services.rnd_graph.runner import mark_run_failed

    mark_run_failed(run_id, exc, context=context)
