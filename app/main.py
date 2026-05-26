"""Application entrypoint.

Wires together configuration, logging, error handlers, routers, and lifecycle hooks.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router_v1
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.cache.redis_client import dispose_redis, get_redis_pool
from app.infrastructure.db.session import dispose_engine, get_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger = get_logger(__name__)
    settings = get_settings()

    logger.info("app.starting", env=settings.app_env, version=settings.app_version)

    # Eagerly initialize pools so first request doesn't pay the latency.
    get_engine()
    get_redis_pool()

    logger.info("app.started")
    yield
    logger.info("app.stopping")

    await dispose_engine()
    await dispose_redis()

    logger.info("app.stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    register_exception_handlers(app)
    app.include_router(api_router_v1, prefix=settings.api_prefix)

    return app


app = create_app()