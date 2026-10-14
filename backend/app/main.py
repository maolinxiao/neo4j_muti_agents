import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_current_admin, get_current_user
from app.api.middleware import ConcurrencyMetricsMiddleware
from app.api.ratelimit import RateLimitMiddleware
from app.api.routes import admin_router, auth_router, chat_router, constitution_router, entity_router, health_router, rnd_router
from app.core.config import settings
from app.db.init_db import initialize_database
from app.db.sqlalchemy import engine
from app.repositories.neo4j_repository import Neo4jRepository


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 请求并发指标：在途/峰值并发与状态码分布 + 慢请求日志，经 /api/health 的 concurrency 字段暴露
    app.add_middleware(ConcurrencyMetricsMiddleware)
    # 应用层每 IP 滑动窗口限流（认证入口更严；RATE_LIMIT_ENABLED 可关）
    app.add_middleware(RateLimitMiddleware)

    protected = [Depends(get_current_user)]
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(chat_router, prefix="/api", dependencies=protected)
    app.include_router(entity_router, prefix="/api", dependencies=protected)
    app.include_router(constitution_router, prefix="/api", dependencies=protected)
    app.include_router(rnd_router, prefix="/api", dependencies=protected)
    # 管理后台：全部端点要求管理员角色（在路由层守护）
    app.include_router(admin_router, prefix="/api", dependencies=[Depends(get_current_admin)])

    # 上传文件（头像等）：挂在 /api 前缀下，走现有 nginx 反代，无需改 nginx
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    @app.on_event("startup")
    def on_startup() -> None:
        initialize_database()
        # PG 连接池预热：启动即建满 pool_size 条连接，避免首个并发峰值的批量建连抖动
        try:
            from sqlalchemy import text

            connections = []
            for _ in range(settings.pg_pool_size):
                conn = engine.connect()
                conn.execute(text("SELECT 1"))
                connections.append(conn)
            for conn in connections:
                conn.close()
            logger.info("PG 连接池预热完成（%s 条）", settings.pg_pool_size)
        except Exception:
            logger.exception("PG 连接池预热失败（将在首个请求时按需建连）")
        try:
            Neo4jRepository().health_check()
        except Exception:
            logger.exception("Neo4j warmup failed")
        # LangGraph 运行期校验（**只读**）：schema 与必需表存在性 + public 无 checkpoint%。
        # 启动路径零 DDL：建表只由 backend/scripts/init_langgraph_checkpoint.py 执行（v2.1 §C.8）。
        if settings.rnd_langgraph_validate_on_start:
            try:
                from app.services.rnd_graph.checkpointer import validate_langgraph_runtime

                status = validate_langgraph_runtime()
                if status.ok:
                    logger.info("langgraph 运行期校验通过：%s", status.describe())
                elif status.error:
                    logger.warning("langgraph 运行期校验未通过（开关为 langgraph 时建 Run 将返回 503）：%s", status.describe())
                else:
                    logger.warning("langgraph schema 不完整（开关为 langgraph 时建 Run 将返回 503）：%s", status.describe())
            except Exception:
                logger.exception("langgraph 运行期校验异常（仅告警，不影响启动）")

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        Neo4jRepository.close_shared_driver()

    return app


app = create_app()
