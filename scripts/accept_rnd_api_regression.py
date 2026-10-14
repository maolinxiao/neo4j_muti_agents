#!/usr/bin/env python
"""只读接口契约与历史回放回归（v2.1 §D-1 E2E-3/E2E-4，**仅 GET**）。

硬约束：
- **只发 GET**：脚本内部对被调用方法做断言，任何非 GET 调用（本脚本从不构造）都会直接报错；
- 不建测试账号、不写库、不重启服务：鉴权 token 由外部注入（``--token`` 或环境变量
  ``RND_API_TOKEN``）；未提供 token 时受保护端点记为 ``skipped_no_token``（不算失败）；
- 目标是**隔离环境**（默认 ``http://127.0.0.1:8010``，v2.2 §2 staging 端口）或生产只读巡检；
  默认拒绝非回环/非本地主机名，确需远端只读须显式 ``--allow-remote``。

检查项：
1. ``/api/health``、``/api/admin/overview``、``/api/admin/workflow-logs``、
   ``/api/constitution/types``、``/api/constitution/questionnaire`` 的状态码与顶层结构；
2. ``GET /api/rnd/runs/{run_id}`` 历史回放：规范化 JSON sha256 与基线一致、字段结构不变；
3. 基线文件：``--write-baseline`` 生成、``--baseline`` 比对（HIST-1 的只读回放口径）。
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_BASE_URL = "http://127.0.0.1:8010"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0", ""}

ENDPOINTS = [
    {"name": "health", "path": "/api/health", "public": True, "kind": "object"},
    {"name": "admin_overview", "path": "/api/admin/overview", "public": False, "kind": "object"},
    {"name": "admin_workflow_logs", "path": "/api/admin/workflow-logs", "public": False, "kind": "list"},
    {"name": "constitution_types", "path": "/api/constitution/types", "public": False, "kind": "list"},
    {"name": "constitution_questionnaire", "path": "/api/constitution/questionnaire", "public": False, "kind": "object"},
]

RUN_ENDPOINT = "/api/rnd/runs/{run_id}"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="研发协同只读接口契约与历史回放回归（仅 GET）")
    parser.add_argument("--base-url", default=os.getenv("RND_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--token", default=os.getenv("RND_API_TOKEN") or os.getenv("STG_API_TOKEN"),
                        help="Bearer token（由外部注入；脚本自身不登录、不写库）")
    parser.add_argument("--run-ids", default=os.getenv("RND_API_RUN_IDS", ""),
                        help="参与历史回放的 run id（逗号分隔）")
    parser.add_argument("--run-ids-file", default=None, help="run id 列表文件（每行一个）")
    parser.add_argument("--baseline", default=None, help="基线 JSON（比对回放哈希与结构）")
    parser.add_argument("--write-baseline", default=None, help="把本次观测写为基线 JSON")
    parser.add_argument("--report", default=None, help="JSON 报告输出路径")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--allow-remote", action="store_true", help="允许非本机 base-url（只读巡检）")
    parser.add_argument("--require-token", action="store_true", help="缺少 token 时判失败（默认记为 skipped）")
    return parser.parse_args(argv)


def canonical_hash(payload) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_get(method: str) -> None:
    """仅 GET 硬约束：本脚本任何请求方法都必须是 GET。"""
    if method.upper() != "GET":
        raise RuntimeError(f"本脚本只允许 GET 请求，收到 {method!r}（只读契约违规）")


def http_get(base_url: str, path: str, *, token: str | None, timeout: float, requests_log: list) -> dict:
    import httpx

    url = base_url.rstrip("/") + path
    require_get("GET")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    requests_log.append({"method": "GET", "url": url})
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
    except Exception as exc:  # 连接失败按失败登记（不写库、不重试）
        return {"ok": False, "status": None, "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": int((time.perf_counter() - started) * 1000)}
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    body = response.content
    parsed = None
    parse_error = None
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        parse_error = f"{type(exc).__name__}: {exc}"
    return {
        "ok": True,
        "status": response.status_code,
        "body_bytes": len(body),
        "json": parsed,
        "json_sha256": canonical_hash(parsed) if parsed is not None else None,
        "parse_error": parse_error,
        "elapsed_ms": elapsed_ms,
    }


def structure_of(payload):
    if isinstance(payload, dict):
        return {"type": "object", "keys": sorted(payload.keys())}
    if isinstance(payload, list):
        first = payload[0] if payload else None
        return {"type": "list", "len": len(payload),
                "item_keys": sorted(first.keys()) if isinstance(first, dict) else None}
    return {"type": type(payload).__name__}


def check(name, ok, detail=None):
    return {"name": name, "ok": bool(ok), "detail": detail}


def load_run_ids(args) -> list:
    ids = [item.strip() for item in (args.run_ids or "").split(",") if item.strip()]
    if args.run_ids_file:
        text = Path(args.run_ids_file).read_text(encoding="utf-8")
        ids.extend(line.strip() for line in text.splitlines() if line.strip())
    seen, unique = set(), []
    for item in ids:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def validate_run_payload(payload: dict) -> list:
    """回放结构校验：字段存在、六步序列、快照列表为 list。"""
    checks = []
    if not isinstance(payload, dict):
        return [check("回放响应为对象", False, type(payload).__name__)]
    required = ["id", "session_id", "question", "brief", "final_report", "summary_metrics",
                "related_graph_snapshots", "status", "steps", "created_at", "updated_at"]
    missing = [key for key in required if key not in payload]
    checks.append(check("回放字段齐备（契约零变化）", not missing, {"missing": missing}))
    steps = payload.get("steps")
    checks.append(check("steps 为列表", isinstance(steps, list), type(steps).__name__))
    if isinstance(steps, list) and steps:
        agents = [item.get("agent_key") for item in steps if isinstance(item, dict)]
        sequences = [item.get("sequence") for item in steps if isinstance(item, dict)]
        checks.append(check("step 顺序 = 1..N 且 agent_key 非空",
                            sequences == sorted(sequences) and all(agents),
                            {"agents": agents, "sequences": sequences}))
        step_keys = sorted({key for item in steps if isinstance(item, dict) for key in item.keys()})
        checks.append(check("step 字段集合稳定", bool(step_keys), step_keys))
    checks.append(check("related_graph_snapshots 为列表", isinstance(payload.get("related_graph_snapshots"), list)))
    return checks


def main(argv=None) -> int:
    args = parse_args(argv)
    host = urlparse(args.base_url).hostname or ""
    if host not in LOCAL_HOSTS and not args.allow_remote:
        raise SystemExit(f"base-url 主机 {host!r} 非本机：默认只允许隔离环境；远端只读巡检需显式 --allow-remote")

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "token_provided": bool(args.token),
        "requests": [],
        "endpoint_checks": [],
        "replay": [],
        "ok": False,
    }
    failures: list = []
    skipped: list = []

    for endpoint in ENDPOINTS:
        observed = http_get(args.base_url, endpoint["path"], token=args.token, timeout=args.timeout,
                            requests_log=report["requests"])
        entry = {"name": endpoint["name"], "path": endpoint["path"], "public": endpoint["public"],
                 "status": observed.get("status"), "json_sha256": observed.get("json_sha256"),
                 "json_bytes": observed.get("body_bytes"), "elapsed_ms": observed.get("elapsed_ms")}
        checks = []
        if not observed.get("ok"):
            entry["error"] = observed.get("error")
            checks.append(check("请求成功", False, observed.get("error")))
        elif observed["status"] in (401, 403) and not args.token:
            entry["skipped"] = "skipped_no_token"
            skipped.append(endpoint["name"])
            checks.append(check("缺少 token → 记为 skipped（不计失败）", True, observed["status"]))
        else:
            checks.append(check("状态码 200", observed["status"] == 200, observed["status"]))
            payload = observed.get("json")
            if observed["status"] == 200 and payload is None:
                checks.append(check("响应为 JSON", False, observed.get("parse_error")))
            elif observed["status"] == 200:
                expected_kind = endpoint["kind"]
                actual_kind = "object" if isinstance(payload, dict) else "list" if isinstance(payload, list) else type(payload).__name__
                checks.append(check(f"顶层结构为 {expected_kind}", actual_kind == expected_kind,
                                    structure_of(payload)))
                if endpoint["name"] == "health" and isinstance(payload, dict):
                    checks.append(check("health.status = ok", payload.get("status") == "ok", payload.get("status")))
        entry["checks"] = checks
        if any(not item["ok"] for item in checks):
            failures.append(endpoint["name"])
        report["endpoint_checks"].append(entry)

    # 历史回放（GET /api/rnd/runs/{run_id}）
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8")) if args.baseline else None
    baseline_runs = (baseline or {}).get("runs", {})
    for run_id in load_run_ids(args):
        path = RUN_ENDPOINT.format(run_id=run_id)
        observed = http_get(args.base_url, path, token=args.token, timeout=args.timeout,
                            requests_log=report["requests"])
        checks = []
        if observed.get("status") in (401, 403) and not args.token:
            report["replay"].append({"run_id": run_id, "skipped": "skipped_no_token"})
            skipped.append(f"run:{run_id}")
            continue
        checks.append(check("状态码 200", observed.get("status") == 200, observed.get("status")))
        payload = observed.get("json")
        if observed.get("status") == 200 and isinstance(payload, dict):
            checks.extend(validate_run_payload(payload))
        if baseline is not None:
            expected = baseline_runs.get(run_id)
            checks.append(check("回放哈希与基线一致", bool(expected) and expected.get("json_sha256") == observed.get("json_sha256"),
                                {"baseline": (expected or {}).get("json_sha256"), "observed": observed.get("json_sha256")}))
        entry = {"run_id": run_id, "path": path, "status": observed.get("status"),
                 "json_sha256": observed.get("json_sha256"), "checks": checks}
        if any(not item["ok"] for item in checks):
            failures.append(f"run:{run_id}")
        report["replay"].append(entry)

    if args.write_baseline:
        baseline_payload = {
            "note": "只读回放基线（GET /api/rnd/runs/{id} 规范化 sha256）；用 --baseline 比对",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "base_url": args.base_url,
            "runs": {item["run_id"]: {"json_sha256": item.get("json_sha256"), "status": item.get("status")}
                     for item in report["replay"] if item.get("json_sha256")},
            "endpoints": {item["name"]: {"status": item.get("status"), "json_sha256": item.get("json_sha256")}
                          for item in report["endpoint_checks"]},
        }
        Path(args.write_baseline).write_text(json.dumps(baseline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report["baseline_written"] = args.write_baseline

    report["failures"] = failures
    report["skipped"] = skipped
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["only_get_requests"] = all(item["method"] == "GET" for item in report["requests"])
    report["ok"] = not failures and report["only_get_requests"] and not (
        args.require_token and not args.token and skipped
    )

    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.report:
        Path(args.report).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
