from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_current_user
from app.api.routes import admin_router, auth_router, chat_router, entity_router, health_router, rnd_router
from app.core.config import settings
from app.db.init_db import initialize_database


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
    app.include_router(rnd_router, prefix="/api", dependencies=protected)
    app.include_router(admin_router, prefix="/api", dependencies=protected)

    @app.on_event("startup")
    def on_startup() -> None:
        initialize_database()

    return app


app = create_app()
