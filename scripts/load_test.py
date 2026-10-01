"""API 并发压测脚本（2026-10-02 负载优化配套验收工具）。

用途：
  1. 常规接口压测：固定总数或固定时长，输出 RPS / P50 / P95 / P99 / 错误率；
  2. SSE 流式接口首包延迟：--sse 模式只测「连接建立到读到首个数据块」的耗时，
     对应问答场景用户感知的等待起点；
  3. --markdown 以表格输出，可直接贴进验收记录。

用法示例：
  python scripts/load_test.py -u http://118.24.185.45 -p /api/health -n 2000 -c 50
  python scripts/load_test.py -u http://127.0.0.1:8000 -p /api/health --duration 30 -c 20
  python scripts/load_test.py -u https://www.mmfh.com.cn -p /api/chat/some-session/messages/stream \
      --sse -c 5 -n 10 -H "Authorization: Bearer <token>"

注意：压测公网会真实消耗服务器资源，验收用小并发短时长即可。
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API 并发压测（RPS/分位数/SSE 首包延迟）")
    parser.add_argument("-u", "--base-url", required=True, help="目标站点，如 http://118.24.185.45")
    parser.add_argument("-p", "--path", default="/api/health", help="压测路径")
    parser.add_argument("-n", "--total", type=int, default=200, help="总请求数（与 --duration 二选一）")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="并发线程数")
    parser.add_argument("--duration", type=float, default=0, help="按秒持续压测（>0 时忽略 -n）")
    parser.add_argument("--timeout", type=float, default=15.0, help="单请求超时（秒）")
    parser.add_argument("--sse", action="store_true", help="SSE 模式：测首包延迟，需 Authorization")
    parser.add_argument("-H", "--header", action="append", default=[], help="附加请求头，可多次，格式 'Name: value'")
    parser.add_argument("--markdown", action="store_true", help="以 Markdown 表格输出结果")
    return parser.parse_args()


def build_headers(raw_headers: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in raw_headers:
        if ":" not in item:
            print(f"[warn] 忽略非法 header：{item}", file=sys.stderr)
            continue
        name, value = item.split(":", 1)
        headers[name.strip()] = value.strip()
    return headers


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, round(pct / 100 * (len(sorted_values) - 1))))
    return sorted_values[index]


def one_request(client: httpx.Client, url: str, sse: bool) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "status": 0, "elapsed_ms": 0.0, "error": ""}
    started = time.perf_counter()
    try:
        if sse:
            with client.stream("GET", url) as response:
                result["status"] = response.status_code
                # 读到第一个非空数据块即算首包（SSE 场景的关键延迟）
                for chunk in response.iter_bytes():
                    if chunk:
                        break
            result["ok"] = response.status_code < 400
        else:
            response = client.get(url)
            result["status"] = response.status_code
            result["ok"] = response.status_code < 400
    except httpx.HTTPError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:120]
    finally:
        result["elapsed_ms"] = (time.perf_counter() - started) * 1000
    return result


def run_load(args: argparse.Namespace, headers: dict[str, str]) -> list[dict[str, Any]]:
    url = args.base_url.rstrip("/") + args.path
    results: list[dict[str, Any]] = []
    timeout = httpx.Timeout(connect=5.0, read=args.timeout, write=10.0, pool=args.timeout)
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)

    print(f"[load] 目标 {url} | 并发 {args.concurrency} | "
          f"{'时长 %.0fs' % args.duration if args.duration > 0 else '总数 %d' % args.total} | "
          f"{'SSE 首包' if args.sse else 'GET'}")
    started = time.perf_counter()
    with httpx.Client(timeout=timeout, limits=limits, verify=False) as client, ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as pool:
        if args.duration > 0:
            def duration_worker() -> list[dict[str, Any]]:
                deadline = time.perf_counter() + args.duration
                batch: list[dict[str, Any]] = []
                while time.perf_counter() < deadline:
                    batch.append(one_request(client, url, args.sse))
                return batch

            futures = [pool.submit(duration_worker) for _ in range(args.concurrency)]
        else:
            # 总数模式：一次性提交全部请求，由线程池按 concurrency 排队调度
            futures = [pool.submit(one_request, client, url, args.sse) for _ in range(args.total)]
        for future in as_completed(futures):
            outcome = future.result()
            if isinstance(outcome, list):
                results.extend(outcome)
            else:
                results.append(outcome)
    wall_seconds = max(1e-6, time.perf_counter() - started)
    results.append({"_wall_seconds": wall_seconds})  # 内部用，汇总时剔除
    return results


def summarize(args: argparse.Namespace, results: list[dict[str, Any]]) -> dict[str, Any]:
    wall = results[-1].get("_wall_seconds", 0.0)
    samples = [r for r in results if "_wall_seconds" not in r]
    latencies = sorted(r["elapsed_ms"] for r in samples)
    ok = sum(1 for r in samples if r.get("ok"))
    status_counts: dict[int, int] = {}
    error_counts: dict[str, int] = {}
    for r in samples:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        if r.get("error"):
            error_counts[r["error"]] = error_counts.get(r["error"], 0) + 1
    metric_label = "SSE 首包 P95 (ms)" if args.sse else "P95 (ms)"
    return {
        "requests": len(samples),
        "concurrency": args.concurrency,
        "rps": round(len(samples) / wall, 1) if wall else 0,
        "p50": round(percentile(latencies, 50), 1),
        "p95": round(percentile(latencies, 95), 1),
        "p99": round(percentile(latencies, 99), 1),
        "ok": ok,
        "errors": len(samples) - ok,
        "metric_label": metric_label,
        "status_counts": status_counts,
        "top_errors": dict(sorted(error_counts.items(), key=lambda kv: -kv[1])[:3]),
        "mean": round(statistics.fmean(latencies), 1) if latencies else 0.0,
    }


def print_report(summary: dict[str, Any], markdown: bool) -> None:
    if markdown:
        print("\n| 指标 | 值 |")
        print("|---|---|")
        print(f"| 请求数 | {summary['requests']} |")
        print(f"| 并发 | {summary['concurrency']} |")
        print(f"| RPS | {summary['rps']} |")
        print(f"| 均值 (ms) | {summary['mean']} |")
        print(f"| P50 (ms) | {summary['p50']} |")
        print(f"| {summary['metric_label']} | {summary['p95']} |")
        print(f"| P99 (ms) | {summary['p99']} |")
        print(f"| 成功 / 失败 | {summary['ok']} / {summary['errors']} |")
        print(f"| 状态码 | {summary['status_counts']} |")
        if summary["top_errors"]:
            print(f"| 高频错误 | {summary['top_errors']} |")
        return
    print("\n===== 压测结果 =====")
    print(f"请求数     : {summary['requests']}（并发 {summary['concurrency']}）")
    print(f"RPS        : {summary['rps']}")
    print(f"延迟均值   : {summary['mean']} ms")
    print(f"P50 / P95 / P99 : {summary['p50']} / {summary['p95']} / {summary['p99']} ms")
    print(f"成功/失败  : {summary['ok']} / {summary['errors']}")
    print(f"状态码分布 : {summary['status_counts']}")
    if summary["top_errors"]:
        print(f"高频错误   : {summary['top_errors']}")


def main() -> int:
    args = parse_args()
    headers = build_headers(args.header)
    if args.sse and "Authorization" not in headers:
        print("[warn] SSE 路径通常需要认证（-H 'Authorization: Bearer ...'），401 会计入失败", file=sys.stderr)
    results = run_load(args, headers)
    summary = summarize(args, results)
    print_report(summary, args.markdown)
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
