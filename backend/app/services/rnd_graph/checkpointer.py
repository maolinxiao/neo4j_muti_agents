"""Checkpointer 工厂与运行期校验（v2.1 §C.8）。

- 连接参数固定为 ``autocommit=True`` + ``row_factory=psycopg.rows.dict_row`` +
  ``options="-c search_path=langgraph,public"``（checkpoint 表的 DDL 是非限定表名 → 落 search_path 首段）；
- **建表只在 CLI**（``backend/scripts/init_langgraph_checkpoint.py``，autocommit，含 ``CREATE INDEX CONCURRENTLY``）；
  本模块只创建连接池与 Saver 实例，不执行任何 DDL；
- ``main.py`` 启动只调用 ``validate_langgraph_runtime()``（只读探测）；
- psycopg / psycopg_pool / langgraph 均为延迟导入，未安装时本模块仍可 import。
"""

import logging
from typing import Any

from app.core.config import settings
from app.db.langgraph_schema import (
    LanggraphSchemaStatus,
    build_search_path,
    dsn_without_driver,
    resolve_schema,
    validate_langgraph_schema,
)

logger = logging.getLogger(__name__)


def psycopg_connection_kwargs(schema: str | None = None) -> dict[str, Any]:
    """统一连接参数（pool kwargs 与直连共用）。

    ``row_factory=psycopg.rows.dict_row``：Saver 期望 dict 行；
    ``options="-c search_path=<schema>,public"``：checkpoint 表用非限定表名，落在 search_path 首段。
    """
    from psycopg.rows import dict_row  # 延迟导入：未装 psycopg 时本模块仍可 import

    return {
        "autocommit": True,
        "row_factory": dict_row,
        "options": f"-c search_path={build_search_path(schema)}",
    }


def build_connection_pool(*, dsn: str | None = None, schema: str | None = None, pool_max: int | None = None):
    """构造 psycopg_pool.ConnectionPool（autocommit + dict_row + search_path）。

    池上限默认 ``settings.rnd_langgraph_pool_max``（2）；PG 连接预算见 v2.1 §C.7。
    """
    from psycopg_pool import ConnectionPool

    resolved_schema = resolve_schema(schema)
    max_size = int(pool_max or settings.rnd_langgraph_pool_max or 2)
    return ConnectionPool(
        conninfo=dsn_without_driver(dsn or settings.postgres_dsn),
        min_size=1,
        max_size=max_size,
        kwargs=psycopg_connection_kwargs(resolved_schema),
        open=True,
    )


def build_checkpointer(*, dsn: str | None = None, schema: str | None = None, pool_max: int | None = None):
    """构造 PostgresSaver（生产路径使用）。

    langgraph-checkpoint-postgres 的签名（P1 锁定版本实测）：
    ``PostgresSaver(conn: Connection | ConnectionPool, pipe=None, serde=None)``，
    ``conn`` 传 psycopg Connection 或 ConnectionPool 均可；建表用 ``PostgresSaver.setup()``（仅 CLI 调用）。
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    pool = build_connection_pool(dsn=dsn, schema=schema, pool_max=pool_max)
    return PostgresSaver(pool)


def validate_langgraph_runtime(*, dsn: str | None = None, schema: str | None = None) -> LanggraphSchemaStatus:
    """FastAPI 启动期校验（**只读**）：schema 与必需表存在性 + ``public`` 无 ``checkpoint%``。

    不建表、不改表；失败只返回状态对象，由调用方决定告警/拒绝（开关为 langgraph 时建 Run 返回 503）。
    """
    return validate_langgraph_schema(dsn=dsn, schema=schema)
