import logging

from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_current_admin, get_current_user
from app.api.routes import admin_router, auth_router, chat_router, constitution_router, entity_router, health_router, rnd_router
from app.core.config import settings
from app.db.init_db import initialize_database
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

    protected = [Depends(get_current_user)]
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(chat_router, prefix="/api", dependencies=protected)
    app.include_router(entity_router, prefix="/api", dependencies=protected)
    app.include_router(constitution_router, prefix="/api", dependencies=protected)
    app.include_router(rnd_router, prefix="/api", dependencies=protected)
    # 管理后台：全部端点要求管理员角色（在路由层守护）
    app.include_router(admin_router, prefix="/api", dependencies=[Depends(get_current_admin)])

    @app.on_event("startup")
    def on_startup() -> None:
        initialize_database()
        try:
            Neo4jRepository().health_check()
        except Exception:
            logger.exception("Neo4j warmup failed")

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        Neo4jRepository.close_shared_driver()

    return app


app = create_app()
