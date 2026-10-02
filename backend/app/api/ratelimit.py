"""应用层每 IP 滑动窗口限流。

定位是「兜底保险丝」而非业务风控：正常用户远达不到阈值，仅在异常洪峰
（脚本扫描、失控前端轮询、被刷的公开接口）时快速失败，保护单 worker
线程池不被无意义请求占满。认证类接口（登录/注册/验证码）使用更严的
独立窗口；/api/health 放行以便监控探活。

实现为进程内滑动窗口（deque 时间戳），单 worker 事件循环内调用无需加锁；
与 uvicorn --limit_concurrency（总并发上限）互补：limit_concurrency 保进程，
限流保行为。可通过 RATE_LIMIT_ENABLED=false 整体关闭。
"""

import logging
import time
from collections import deque
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


logger = logging.getLogger(__name__)

# 更严窗口的路径前缀：认证与公开敏感入口
STRICT_PATH_PREFIXES = (
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/captcha",
    "/api/auth/change-password",
)

# 监控放行路径
EXEMPT_PATHS = {"/api/health"}


class SlidingWindowCounter:
    """按 key（这里是客户端 IP）维护滑动窗口内的请求时间戳。"""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def _prune(self, key: str, now: float) -> deque[float]:
        window = self._hits.get(key)
        if window is None:
            window = deque()
            self._hits[key] = window
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        return window

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window = self._prune(key, now)
        if len(window) >= self.max_requests:
            return False
        window.append(now)
        return True

    def retry_after(self, key: str) -> int:
        """估算该 key 还需等待多少秒才可能有空位。"""
        now = time.monotonic()
        window = self._hits.get(key)
        if not window:
            return 0
        oldest = window[0]
        wait = self.window_seconds - (now - oldest)
        return max(1, int(wait) + 1)

    def stats(self) -> dict[str, Any]:
        return {
            "tracked_keys": len(self._hits),
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.default_limiter = SlidingWindowCounter(
            settings.rate_limit_requests,
            settings.rate_limit_window_seconds,
        )
        self.strict_limiter = SlidingWindowCounter(
            settings.rate_limit_auth_requests,
            settings.rate_limit_auth_window_seconds,
        )

    def _client_key(self, request: Request) -> str:
        # nginx 反代会带 X-Real-IP；本地直连时回落 remote_addr
        forwarded = request.headers.get("x-real-ip")
        if forwarded:
            return forwarded.strip()
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.rate_limit_enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        key = self._client_key(request)
        path = request.url.path
        limiter = (
            self.strict_limiter
            if any(path.startswith(prefix) for prefix in STRICT_PATH_PREFIXES)
            else self.default_limiter
        )
        if not limiter.allow(key):
            retry_after = limiter.retry_after(key)
            logger.warning(
                "限流触发：ip=%s path=%s 规则=%s/%ss，Retry-After=%ss",
                key,
                path,
                limiter.max_requests,
                limiter.window_seconds,
                retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试。"},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
