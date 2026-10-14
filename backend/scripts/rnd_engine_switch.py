#!/usr/bin/env python
"""引擎开关切换 / 回滚脚本（v2.1 §B.1，运维用；**不含任何凭据**）。

行为：读旧值 → 写新值 → 打印**回滚命令**（旧值或"删除该行"），供 §E.6 R1 使用。

口径（写入 ``system_config.rnd_engine``）：
- ``legacy``：全局 legacy（默认，等价于删除该行）；
- ``canary``：``{"mode":"canary","users":[...]}``，白名单用户走 langgraph；
- ``langgraph``：全局 langgraph。

安全前置：切到 langgraph/canary 前先做一次只读 schema 校验；不通过则拒绝（除非 ``--force``）。

用法：
  python backend/scripts/rnd_engine_switch.py --show
  python backend/scripts/rnd_engine_switch.py --set '{"mode":"canary","users":["<uuid>"]}'
  python backend/scripts/rnd_engine_switch.py --set-mode langgraph
  python backend/scripts/rnd_engine_switch.py --delete          # 等同回滚到默认 legacy
"""

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.langgraph_schema import dsn_without_driver, resolve_schema, validate_langgraph_schema  # noqa: E402

ENGINE_KEY = "rnd_engine"
MIGRATED_AT_KEY = "rnd_engine_migrated_at"


def _connect(dsn: str, schema: str):
    import psycopg

    return psycopg.connect(
        dsn_without_driver(dsn), autocommit=True, options=f"-c search_path={schema},public"
    )


def read_value(conn, key: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT config_value FROM public.system_config WHERE config_key = %s", (key,))
        row = cur.fetchone()
    return row[0] if row else None


def write_value(conn, key: str, value: str | None) -> None:
    """value=None → 删除该行（回滚到默认 legacy）。"""
    with conn.cursor() as cur:
        if value is None:
            cur.execute("DELETE FROM public.system_config WHERE config_key = %s", (key,))
            return
        cur.execute(
            "INSERT INTO public.system_config (id, config_key, config_value, config_type, created_at, updated_at) "
            "VALUES (gen_random_uuid()::text, %s, %s, 'string', now(), now()) "
            "ON CONFLICT (config_key) DO UPDATE SET config_value = EXCLUDED.config_value, updated_at = now()",
            (key, value),
        )


def build_value(mode: str, users: list[str] | None) -> str:
    normalized = mode.strip().lower()
    if normalized == "legacy":
        return "legacy"
    if normalized == "langgraph":
        return "langgraph"
    if normalized == "canary":
        return json.dumps({"mode": "canary", "users": users or []}, ensure_ascii=False)
    raise SystemExit(f"不支持的 mode：{mode}（可选 legacy/canary/langgraph）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="研发协同引擎开关切换/回滚（默认 legacy）")
    parser.add_argument("--db-url", default=os.getenv("POSTGRES_DSN") or settings.postgres_dsn)
    parser.add_argument("--schema", default=settings.rnd_langgraph_schema)
    parser.add_argument("--show", action="store_true", help="只读显示当前值与 marker")
    parser.add_argument("--set", dest="set_value", default=None, help="直接写入原始值")
    parser.add_argument("--set-mode", dest="set_mode", default=None, choices=["legacy", "canary", "langgraph"])
    parser.add_argument("--users", default="", help="canary 白名单 user_id（逗号分隔）")
    parser.add_argument("--delete", action="store_true", help="删除该行（回滚到默认 legacy）")
    parser.add_argument("--force", action="store_true", help="跳过 langgraph schema 只读校验")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    schema = resolve_schema(args.schema)
    conn = _connect(args.db_url, schema)
    try:
        old_value = read_value(conn, ENGINE_KEY)
        marker = read_value(conn, MIGRATED_AT_KEY)
        payload: dict = {"schema": schema, "old_value": old_value, "migrated_at": marker}

        if args.show or not any([args.set_value is not None, args.set_mode, args.delete]):
            status = validate_langgraph_schema(dsn=args.db_url, schema=schema)
            payload.update({"mode": "show", "schema_status": status.as_dict()})
            payload["rollback_command"] = _rollback_hint(old_value)
            _emit(payload, args.json)
            return 0

        if args.delete:
            new_value: str | None = None
        elif args.set_value is not None:
            new_value = args.set_value
        else:
            users = [item.strip() for item in (args.users or "").split(",") if item.strip()]
            new_value = build_value(args.set_mode, users)

        wants_langgraph = bool(new_value) and new_value not in ("legacy", "")
        if wants_langgraph and not args.force:
            status = validate_langgraph_schema(dsn=args.db_url, schema=schema)
            if not status.ok:
                payload.update(
                    {
                        "mode": "refused",
                        "reason": "langgraph schema 校验未通过，拒绝切换（可用 --force 跳过）",
                        "schema_status": status.as_dict(),
                    }
                )
                _emit(payload, args.json)
                return 3
            if marker is None:
                payload.update(
                    {
                        "mode": "refused",
                        "reason": "缺少 marker rnd_engine_migrated_at（引导段②未成功），拒绝切换",
                    }
                )
                _emit(payload, args.json)
                return 4

        write_value(conn, ENGINE_KEY, new_value)
        payload.update(
            {
                "mode": "write",
                "new_value": new_value,
                "rollback_command": _rollback_hint(old_value),
                "note": "配置生效延迟 ≤ rnd_engine_cache_ttl_seconds（默认 15s），无需重启",
            }
        )
        _emit(payload, args.json)
        return 0
    finally:
        conn.close()


def _rollback_hint(old_value: str | None) -> str:
    """R1 配置回滚：恢复旧值或删除该行。"""
    if old_value is None:
        return "python backend/scripts/rnd_engine_switch.py --delete   # 旧值不存在：删除该行即回退默认 legacy"
    return f"python backend/scripts/rnd_engine_switch.py --set {json.dumps(old_value, ensure_ascii=False)}"


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return
    for key, value in payload.items():
        print(f"{key}: {json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value}")


if __name__ == "__main__":
    raise SystemExit(main())
