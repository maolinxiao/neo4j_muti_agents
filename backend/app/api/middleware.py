"""请求并发指标与慢请求观测中间件。

- ConcurrencyMetrics：统计在途请求数、峰值并发、状态码分布，经 /api/health 的
  concurrency 字段暴露，用于负载观测与 uvicorn --limit-concurrency 过载保护的效果确认。
- SlowRequestMiddleware：超过 slow_request_ms 的请求记 warning（方法、路径、状态码、
  耗时），便于从海量 access log 里直接定位拖慢线程池的接口。

单 worker 事件循环内运行；指标更新发生在事件循环线程，无需加锁。
"""

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


logger = logging.getLogger(__name__)


class ConcurrencyMetrics:
    def __init__(self) -> None:
        self.active_requests = 0
        self.total_requests = 0
        self.peak_concurrency = 0
        self.status_counts: dict[int, int] = {}
        self.started_at = time.time()

    def acquire(self) -> None:
        self.active_requests += 1
        self.total_requests += 1
        if self.active_requests > self.peak_concurrency:
            self.peak_concurrency = self.active_requests

    def release(self, status_code: int) -> None:
        self.active_requests = max(0, self.active_requests - 1)
        self.status_counts[status_code] = self.status_counts.get(status_code, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "peak_concurrency": self.peak_concurrency,
            "uptime_seconds": int(time.time() - self.started_at),
            "status_counts": dict(sorted(self.status_counts.items())),
        }


concurrency_metrics = ConcurrencyMetrics()


class ConcurrencyMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        concurrency_metrics.acquire()
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            concurrency_metrics.release(500)
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000
        concurrency_metrics.release(response.status_code)
        if elapsed_ms >= settings.slow_request_ms:
            logger.warning(
                "慢请求 %.0fms（阈值 %sms）：%s %s -> %s",
                elapsed_ms,
                settings.slow_request_ms,
                request.method,
                request.url.path,
                response.status_code,
            )
        return response
