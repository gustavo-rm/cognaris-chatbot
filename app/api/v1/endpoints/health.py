"""Health endpoints.

- /live: process is up (no dependencies checked).
- /ready: process plus its critical dependencies are healthy.
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import db_session_dep
from app.core.config import get_settings
from app.infrastructure.cache.redis_client import check_redis_health
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])


@router.get("/live")
async def liveness() -> dict:
    settings = get_settings()
    return {
        "status": "up",
        "service": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
    }


@router.get("/ready")
async def readiness(
    session: AsyncSession = Depends(db_session_dep),
) -> dict:
    db_status = "down"
    try:
        await session.execute(text("SELECT 1"))
        db_status = "up"
    except Exception:
        db_status = "down"

    try:
        await check_redis_health()
        redis_status = "up"
    except Exception:
        redis_status = "down"

    overall = "up" if db_status == "up" and redis_status == "up" else "degraded"

    return {
        "status": overall,
        "dependencies": {
            "database": db_status,
            "redis": redis_status,
        },
    }