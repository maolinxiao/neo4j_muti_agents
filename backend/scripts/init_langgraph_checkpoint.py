#!/usr/bin/env python
"""langgraph schema 引导 CLI —— **唯一建表入口**（v2.1 §C.8/§C.5）。

阶段（严格顺序）：
  段①（autocommit）：``CREATE SCHEMA IF NOT EXISTS langgraph`` → ``run_engine``/``run_lock`` DDL
                     → ``PostgresSaver.setup()``（内含 ``CREATE INDEX CONCURRENTLY``，**不能落事务**）
  段②（独立事务）：写 marker ``system_config.rnd_engine_migrated_at``

硬约束：
- 只有本 CLI 建表；FastAPI 启动只做只读校验（``app/services/rnd_graph/checkpointer.py``）；
- 段②失败 → 开关必须保持 legacy（**引导顺序硬约束**：段①建对象 → 段②写 marker 成功 → 才允许开启开关）；
- 不打印任何凭据；DSN 取自 ``--db-url`` 或环境变量/``settings``。

用法：
  python backend/scripts/init_langgraph_checkpoint.py \
      --db-url postgresql+psycopg://postgres@127.0.0.1:5432/neo4j_agents_migrate
  python backend/scripts/init_langgraph_checkpoint.py --print-only     # 只打印现状（只读）
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.langgraph_schema import (  # noqa: E402
    CREATE_SCHEMA_SQL,
    REQUIRED_TABLES,
    RUN_ENGINE_DDL,
    RUN_LOCK_DDL,
    dsn_without_driver,
    resolve_schema,
    validate_langgraph_schema,
)

logger = logging.getLogger("init_langgraph_checkpoint")

MIGRATED_AT_KEY = "rnd_engine_migrated_at"


def _connect(dsn: str, schema: str):
    """autocommit 连接（DDL 与 ``CREATE INDEX CONCURRENTLY`` 的硬要求）。"""
    import psycopg

    return psycopg.connect(
        dsn_without_driver(dsn),
        autocommit=True,
        options=f"-c search_path={schema},public",
    )


def bootstrap_objects(*, dsn: str, schema: str, app_user: str | None = None, dry_run: bool = False) -> dict:
    """段①：建 schema + run_engine/run_lock + 4 张 checkpoint 表（autocommit，无事务包裹）。"""
    resolved = resolve_schema(schema)
    statements = [CREATE_SCHEMA_SQL.format(schema=resolved)]
    if app_user:
        from app.db.langgraph_schema import is_valid_identifier

        if not is_valid_identifier(app_user):
            raise ValueError(f"非法应用用户标识符：{app_user!r}")
        statements.append(f'ALTER SCHEMA "{resolved}" OWNER TO "{app_user}"')
    statements.append(RUN_ENGINE_DDL.format(schema=resolved))
    statements.append(RUN_LOCK_DDL.format(schema=resolved))
    if dry_run:
        return {"dry_run": True, "statements": statements}

    from langgraph.checkpoint.postgres import PostgresSaver

    with _connect(dsn, resolved) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        # setup() 内含 CREATE INDEX CONCURRENTLY：autocommit 连接下逐条执行，不能落事务
        saver = PostgresSaver(conn)
        saver.setup()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name",
                (resolved,),
            )
            tables = [row[0] for row in cur.fetchall()]
    return {"dry_run": False, "schema": resolved, "tables": tables, "statements": statements}


def write_migrated_marker(*, dsn: str, schema: str, dry_run: bool = False) -> dict:
    """段②：独立事务写 ``rnd_engine_migrated_at``（存在则跳过，保持首次迁移时刻不变）。"""
    resolved = resolve_schema(schema)
    if dry_run:
        return {"dry_run": True, "written": False}
    import psycopg

    # 不带 autocommit：让 BEGIN/COMMIT 成为独立事务（与段①的 autocommit 明确分开）
    with psycopg.connect(dsn_without_driver(dsn), options=f"-c search_path={resolved},public") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.system_config') AS oid")
            row = cur.fetchone()
            if row is None or row[0] is None:
                conn.rollback()
                return {"written": False, "skipped": "public.system_config 不存在（先跑 initialize_database）"}
            cur.execute(
                "INSERT INTO public.system_config (id, config_key, config_value, config_type, created_at, updated_at) "
                "VALUES (gen_random_uuid()::text, %s, now()::text, 'string', now(), now()) "
                "ON CONFLICT (config_key) DO NOTHING",
                (MIGRATED_AT_KEY,),
            )
            inserted = cur.rowcount
            cur.execute("SELECT config_value FROM public.system_config WHERE config_key = %s", (MIGRATED_AT_KEY,))
            value_row = cur.fetchone()
            conn.commit()
    return {"written": bool(inserted), "value": value_row[0] if value_row else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="引导 langgraph schema（唯一建表入口）")
    parser.add_argument("--db-url", default=os.getenv("POSTGRES_DSN") or settings.postgres_dsn,
                        help="SQLAlchemy/libpq DSN（默认取 POSTGRES_DSN/settings）")
    parser.add_argument("--schema", default=settings.rnd_langgraph_schema, help="目标 schema（默认 langgraph）")
    parser.add_argument("--app-user", default=None, help="可选：把 schema owner 设为该应用用户")
    parser.add_argument("--print-only", action="store_true", help="只打印现状（只读校验，不建表）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将执行的 DDL，不执行")
    parser.add_argument("--skip-marker", action="store_true", help="只建对象，不写 rnd_engine_migrated_at")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    schema = resolve_schema(args.schema)
    result: dict = {"schema": schema, "db_hint": validate_langgraph_schema(dsn=args.db_url, schema=schema).dsn_hint}

    if args.print_only:
        status = validate_langgraph_schema(dsn=args.db_url, schema=schema)
        result.update(
            {
                "mode": "print-only",
                "status": status.as_dict(),
                "required_tables": list(REQUIRED_TABLES),
            }
        )
        _emit(result, args.json)
        return 0 if status.ok else 1

    try:
        bootstrap = bootstrap_objects(
            dsn=args.db_url, schema=schema, app_user=args.app_user, dry_run=args.dry_run
        )
    except Exception as exc:  # 段①失败：不写 marker，开关必须保持 legacy
        logger.exception("段① 建对象失败（marker 未写入，开关必须保持 legacy）")
        _emit({**result, "ok": False, "stage": "bootstrap", "error": f"{type(exc).__name__}: {exc}"}, args.json)
        return 2

    marker: dict = {"written": False, "skipped": "skip-marker"}
    if not args.skip_marker:
        try:
            marker = write_migrated_marker(dsn=args.db_url, schema=schema, dry_run=args.dry_run)
        except Exception as exc:  # 段②失败：允许重跑，开关保持 legacy
            logger.exception("段② 写 marker 失败（开关必须保持 legacy，可重跑本 CLI）")
            _emit(
                {**result, "ok": False, "stage": "marker", "bootstrap": bootstrap, "error": f"{type(exc).__name__}: {exc}"},
                args.json,
            )
            return 3

    status = validate_langgraph_schema(dsn=args.db_url, schema=schema)
    result.update(
        {
            "mode": "bootstrap",
            "bootstrap": bootstrap,
            "marker": marker,
            "status": status.as_dict(),
            "required_tables": list(REQUIRED_TABLES),
            "ok": status.ok,
            "next_step": "段①建对象成功且段②写 marker 成功后，才允许把 system_config.rnd_engine 切到 langgraph",
        }
    )
    _emit(result, args.json)
    return 0 if status.ok else 4


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return
    for key, value in payload.items():
        print(f"{key}: {json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value}")


if __name__ == "__main__":
    raise SystemExit(main())
