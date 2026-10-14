"""langgraph 独立 schema 的**只读校验**与 DDL 常量（v2.1 §C.8）。

硬约定：
- 本模块**只提供校验**（schema 存在、表存在、只读探测、``public`` 无 ``checkpoint%``）；
  启动路径（``main.py``）零 DDL；建表**只由** ``backend/scripts/init_langgraph_checkpoint.py`` 执行。
- DDL 常量供 CLI 复用；``PostgresSaver.setup()`` 内含 ``CREATE INDEX CONCURRENTLY``，
  因此建表必须在 autocommit 连接上执行，不能落在事务里。
- 已知限制：官方"可配置 schema"仍为开放需求（langgraph#7345），故用连接 ``options="-c search_path=langgraph,public"``
  实现隔离并**显式断言**新表全部落在 ``langgraph``、``public`` 内不得出现 ``checkpoint%``。
- 延迟导入 psycopg：保证未装可选依赖时本模块仍可 import（启动只校验、失败仅告警）。
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)


DEFAULT_SCHEMA = "langgraph"
#: 库自带的 4 张 checkpoint 表（由 PostgresSaver.setup() 创建，非限定表名 → 落在 search_path 首段）
CHECKPOINT_TABLES: tuple[str, ...] = (
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
)
#: 本迁移新增的两张表
RUN_ENGINE_TABLE = "run_engine"
RUN_LOCK_TABLE = "run_lock"
#: 迁移相关表（run_engine）
MIGRATION_TABLES: tuple[str, ...] = (RUN_ENGINE_TABLE,)
#: 全部必须存在的表（4 张 checkpoint + run_engine + run_lock）
REQUIRED_TABLES: tuple[str, ...] = CHECKPOINT_TABLES + (RUN_ENGINE_TABLE, RUN_LOCK_TABLE)
#: v2.1 口径里的"5 张表" = 4 张 checkpoint 表 + run_engine（run_lock 一并校验，属第 6 张）
CORE_FIVE_TABLES: tuple[str, ...] = CHECKPOINT_TABLES + (RUN_ENGINE_TABLE,)

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS {schema}"

RUN_ENGINE_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.run_engine (
  run_id    TEXT PRIMARY KEY,
  engine    TEXT NOT NULL,
  pinned_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

RUN_LOCK_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.run_lock (
  run_id      TEXT PRIMARY KEY,
  owner       TEXT NOT NULL,
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at  TIMESTAMPTZ NOT NULL
)
"""

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_valid_identifier(value: str) -> bool:
    """schema/表名等标识符白名单校验（DDL 常量与 SQL 拼接前必须通过）。"""
    return bool(value) and bool(_IDENT_RE.match(value))


def dsn_without_driver(dsn: str) -> str:
    """SQLAlchemy DSN → libpq DSN：``postgresql+psycopg://`` → ``postgresql://``（psycopg3 直连）。"""
    if dsn.startswith("postgresql+psycopg://"):
        return "postgresql://" + dsn[len("postgresql+psycopg://") :]
    if dsn.startswith("postgres+psycopg://"):
        return "postgres://" + dsn[len("postgres+psycopg://") :]
    return dsn


def resolve_schema(schema: str | None = None) -> str:
    """取生效 schema（默认 settings.rnd_langgraph_schema），并做标识符校验。"""
    resolved = schema or settings.rnd_langgraph_schema or DEFAULT_SCHEMA
    if not is_valid_identifier(resolved):
        raise ValueError(f"非法 schema 名：{resolved!r}")
    return resolved


def build_search_path(schema: str | None = None) -> str:
    """连接 options 用的 search_path：``<schema>,public``（checkpoint 表为非限定名 → 落首段）。"""
    return f"{resolve_schema(schema)},public"


@dataclass
class LanggraphSchemaStatus:
    """只读校验结果（启动告警与验收断言共用）。"""

    schema: str
    dsn_hint: str = ""
    schema_present: bool = False
    tables: list[str] = field(default_factory=list)
    missing_tables: list[str] = field(default_factory=list)
    public_checkpoint_tables: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.schema_present
            and not self.missing_tables
            and not self.public_checkpoint_tables
            and self.error is None
        )

    def describe(self) -> str:
        if self.error:
            return f"langgraph schema 校验失败（{self.schema}）：{self.error}"
        return (
            f"langgraph schema={self.schema} present={self.schema_present} tables={len(self.tables)} "
            f"missing={self.missing_tables} public_checkpoint_tables={self.public_checkpoint_tables}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_present": self.schema_present,
            "tables": list(self.tables),
            "missing_tables": list(self.missing_tables),
            "public_checkpoint_tables": list(self.public_checkpoint_tables),
            "error": self.error,
            "ok": self.ok,
        }


def _connect(dsn: str, *, schema: str, autocommit: bool):
    """建立 psycopg 连接（延迟导入 psycopg；dict_row + search_path 与 checkpointer 保持一致）。"""
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(
        dsn_without_driver(dsn),
        autocommit=autocommit,
        row_factory=dict_row,
        options=f"-c search_path={schema},public",
    )


def list_schema_tables(conn: Any, schema: str) -> list[str]:
    """列出某 schema 下的普通表（只读）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name",
            (schema,),
        )
        return [row["table_name"] for row in cur.fetchall()]


def list_public_checkpoint_tables(conn: Any) -> list[str]:
    """列出 ``public`` 内的 ``checkpoint%`` 表（必须为空；只读）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'checkpoint%%' ORDER BY table_name"
        )
        return [row["table_name"] for row in cur.fetchall()]


def validate_langgraph_schema(
    *,
    dsn: str | None = None,
    schema: str | None = None,
    required_tables: Sequence[str] = REQUIRED_TABLES,
) -> LanggraphSchemaStatus:
    """只读校验：schema 存在、必需表存在、只读探测、``public`` 无 ``checkpoint%``。

    **不执行任何 DDL**；任何异常都收敛为 ``status.error``（启动路径据此告警，不抛出）。
    """
    resolved_schema = resolve_schema(schema)
    dsn = dsn or settings.postgres_dsn
    status = LanggraphSchemaStatus(schema=resolved_schema, dsn_hint=_dsn_hint(dsn))
    try:
        with _connect(dsn, schema=resolved_schema, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database() AS db, 1 AS ok")
                cur.fetchone()
            tables = list_schema_tables(conn, resolved_schema)
            status.tables = tables
            status.schema_present = bool(tables) or _schema_exists(conn, resolved_schema)
            status.missing_tables = [name for name in required_tables if name not in tables]
            status.public_checkpoint_tables = list_public_checkpoint_tables(conn)
    except Exception as exc:  # pragma: no cover - 依赖缺失/连库失败时只告警
        status.error = f"{type(exc).__name__}: {exc}"
    return status


def _schema_exists(conn: Any, schema: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 AS ok FROM information_schema.schemata WHERE schema_name = %s", (schema,))
        return cur.fetchone() is not None


def _dsn_hint(dsn: str) -> str:
    """脱敏的 DSN 摘要（日志/报告用；不含口令）。"""
    text = dsn_without_driver(dsn)
    if "@" in text:
        prefix, _, host_part = text.rpartition("@")
        scheme = prefix.split("://", 1)[0]
        user = prefix.split("://", 1)[-1].split(":", 1)[0]
        return f"{scheme}://{user}@{host_part}"
    return text
