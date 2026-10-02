import sys
from pathlib import Path

# 确保 backend 目录在 sys.path 中（面板托管启动时 CWD 不一定是项目目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        # 负载优化（2026-10-02）：单 worker 形态下的排队容量、过载保护与 keepalive 节奏。
        # 参数在 core/config.py 配置化：APP_BACKLOG / APP_LIMIT_CONCURRENCY / APP_KEEPALIVE_TIMEOUT。
        backlog=settings.app_backlog,
        limit_concurrency=settings.app_limit_concurrency,
        timeout_keep_alive=settings.app_keepalive_timeout,
    )
