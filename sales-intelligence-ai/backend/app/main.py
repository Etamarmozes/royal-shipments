from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .ingestion.folder_watcher import start_watcher, stop_watcher
from .routers import ai as ai_router
from .routers import dashboard as dashboard_router
from .routers import data as data_router
from .routers import health as health_router
from .routers import imports as imports_router
from .routers import reports as reports_router
from .utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    start_watcher()
    yield
    stop_watcher()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sales Intelligence AI",
        version="0.1.0",
        description="Retail sales intelligence command center",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router.router)
    app.include_router(dashboard_router.router)
    app.include_router(imports_router.router)
    app.include_router(ai_router.router)
    app.include_router(reports_router.router)
    app.include_router(data_router.router)
    return app


app = create_app()
