"""Common FastAPI dependencies.

Re-exports the few things endpoints need so we have one canonical import path.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.cache.redis_client import get_redis_client
from app.infrastructure.db.session import get_db_session


async def db_session_dep() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def redis_dep():
    return get_redis_client()