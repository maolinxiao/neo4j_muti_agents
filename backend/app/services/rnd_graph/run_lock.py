"""Run 级独占租约锁（v2.1 §C.3）。

第一阶段口径（严格执行）：
- 领取：``INSERT ... ON CONFLICT (run_id) DO NOTHING RETURNING owner``；
  **只要存在锁行（含已过期）即放弃投递**并 WARN，**不改 Run 状态、不自动接管**；
- 释放：``DELETE WHERE run_id=%s AND owner=%s``（成功/失败/异常都执行）；
- **不实现 fencing token**（阶段二才允许自动接管，且必须先有单调递增 token + 每次业务写入校验）；
- 作用域仅 langgraph 路径；legacy 行为完全不变。
- 心跳每 30s、租约 180s（仅续租，不参与接管判定）。
"""

import logging
import threading
from typing import Any, Callable

from sqlalchemy import text

from app.core.config import settings
from app.db.langgraph_schema import RUN_LOCK_TABLE, resolve_schema

logger = logging.getLogger(__name__)


DEFAULT_LEASE_SECONDS = 180
HEARTBEAT_INTERVAL_SECONDS = 30


def _table(schema: str | None = None) -> str:
    return f"{resolve_schema(schema)}.{RUN_LOCK_TABLE}"


def acquire_lock(
    session: Any,
    run_id: str,
    owner_token: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    schema: str | None = None,
) -> bool:
    """尝试领取租约；返回是否取得执行权。

    有返回行 ⇒ 取得执行权；无返回行 ⇒ 已有锁行（含已过期）⇒ 调用方必须放弃投递并 WARN。
    """
    sql = text(
        f"INSERT INTO {_table(schema)} (run_id, owner, expires_at) "
        "VALUES (:run_id, :owner, now() + make_interval(secs => :lease_seconds)) "
        "ON CONFLICT (run_id) DO NOTHING "
        "RETURNING owner"
    )
    row = session.execute(
        sql, {"run_id": run_id, "owner": owner_token, "lease_seconds": int(lease_seconds)}
    ).fetchone()
    return row is not None


def read_lock(session: Any, run_id: str, *, schema: str | None = None) -> dict[str, Any] | None:
    """读取锁行（只读；人工处理与恢复前置校验用）。"""
    sql = text(
        f"SELECT run_id, owner, acquired_at, heartbeat_at, expires_at "
        f"FROM {_table(schema)} WHERE run_id = :run_id"
    )
    row = session.execute(sql, {"run_id": run_id}).mappings().fetchone()
    return dict(row) if row is not None else None


def release_lock(session: Any, run_id: str, owner_token: str, *, schema: str | None = None) -> bool:
    """按 owner 释放租约；返回是否删除了锁行。"""
    sql = text(f"DELETE FROM {_table(schema)} WHERE run_id = :run_id AND owner = :owner")
    result = session.execute(sql, {"run_id": run_id, "owner": owner_token})
    return bool(result.rowcount)


def heartbeat(session: Any, run_id: str, owner_token: str, *, lease_seconds: int = DEFAULT_LEASE_SECONDS,
              schema: str | None = None) -> bool:
    """续租（仅 owner 自己可续）；返回是否命中锁行。"""
    sql = text(
        f"UPDATE {_table(schema)} SET heartbeat_at = now(), "
        "expires_at = now() + make_interval(secs => :lease_seconds) "
        "WHERE run_id = :run_id AND owner = :owner"
    )
    result = session.execute(
        sql, {"run_id": run_id, "owner": owner_token, "lease_seconds": int(lease_seconds)}
    )
    return bool(result.rowcount)


class LeaseHeartbeat:
    """后台续租线程：每 ``interval`` 秒续租一次，异常只告警，绝不影响 Run 主流程。

    - 线程内自开短会话（不跨线程共享 Session）；
    - ``daemon=True``；``stop()`` 幂等，最多等 ``join_timeout`` 秒。
    """

    def __init__(
        self,
        session_factory: Callable[[], Any],
        run_id: str,
        owner_token: str,
        *,
        interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        schema: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._run_id = run_id
        self._owner_token = owner_token
        self._interval = max(1, int(interval_seconds))
        self._lease_seconds = int(lease_seconds)
        self._schema = schema
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.failures = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name=f"rnd-lock-heartbeat-{self._run_id[:8]}", daemon=True)
        self._thread.start()

    def stop(self, *, join_timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=join_timeout)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            session = None
            try:
                session = self._session_factory()
                heartbeat(
                    session,
                    self._run_id,
                    self._owner_token,
                    lease_seconds=self._lease_seconds,
                    schema=self._schema,
                )
                session.commit()
            except Exception:  # pragma: no cover - 续租失败不影响主流程
                self.failures += 1
                logger.warning(
                    "langgraph run_lock 心跳失败 run_id=%s owner=%s failures=%s",
                    self._run_id,
                    self._owner_token,
                    self.failures,
                    exc_info=True,
                )
            finally:
                if session is not None:
                    try:
                        session.close()
                    except Exception:  # pragma: no cover
                        pass


def lock_schema_ready(session: Any, *, schema: str | None = None) -> bool:
    """只读探测：run_lock 表是否存在（runner/验收脚本据此给出明确报错）。"""
    sql = text("SELECT to_regclass(:qualified) AS oid")
    row = session.execute(sql, {"qualified": _table(schema)}).fetchone()
    return row is not None and row[0] is not None


def log_lock_skipped(run_id: str, owner_token: str, existing: dict[str, Any] | None) -> None:
    """放弃投递时的 WARN（不改 Run 状态；人工处理见 v2.1 §C.3）。"""
    logger.warning(
        "langgraph run_lock held, skip dispatch run_id=%s owner=%s existing_owner=%s expires_at=%s",
        run_id,
        owner_token,
        (existing or {}).get("owner"),
        (existing or {}).get("expires_at"),
    )


def current_schema() -> str:
    """当前生效 schema（日志用）。"""
    return settings.rnd_langgraph_schema
