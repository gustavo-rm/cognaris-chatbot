"""Integration test fixtures using testcontainers.

Spin up real Postgres + Redis once per session, apply Alembic migrations,
and provide an AsyncSession + Redis client to tests.

Tests are isolated by wrapping each in a transaction that's rolled back.
"""
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.core.config import get_settings


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_container() -> RedisContainer:
    with RedisContainer("redis:7-alpine") as r:
        yield r


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    sync_url = postgres_container.get_connection_url()
    # testcontainers returns a psycopg2 URL; switch to asyncpg.
    return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session")
def redis_url(redis_container: RedisContainer) -> str:
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session", autouse=True)
def _apply_settings(database_url: str, redis_url: str) -> None:
    import os

    os.environ["DATABASE_URL"] = database_url
    os.environ["REDIS_URL"] = redis_url
    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(database_url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def db_session(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(database_url, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client(redis_url: str) -> AsyncGenerator[redis_async.Redis, None]:
    client = redis_async.from_url(redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()