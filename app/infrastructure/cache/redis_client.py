"""Redis client wrapper.

Used in later phases for:
- hot session state caching,
- idempotency keys,
- rate limit counters,
- pub/sub for streaming responses.

For now it just exposes a connection pool with health-check.
"""
from typing import Any

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import get_settings
from app.core.exceptions import DependencyUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

_pool: ConnectionPool | None = None


def _build_pool() -> ConnectionPool:
    settings = get_settings()
    return ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        decode_responses=True,
    )


def get_redis_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = _build_pool()
        logger.info("redis.pool.created")
    return _pool


def get_redis_client() -> redis.Redis:
    """Return a Redis client bound to the shared pool."""
    return redis.Redis(connection_pool=get_redis_pool())


async def check_redis_health() -> dict[str, Any]:
    """Liveness check for Redis. Used by /health."""
    client = get_redis_client()
    try:
        await client.ping()
        return {"status": "up"}
    except Exception as exc:
        logger.warning("redis.health.failed", error=str(exc))
        raise DependencyUnavailableError("Redis unreachable") from exc


async def dispose_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("redis.pool.disposed")