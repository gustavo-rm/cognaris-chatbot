"""Integration tests for PgSessionRepository against real Postgres + Redis."""
from uuid import uuid4

import pytest

from app.domain.events import DomainEvent, SessionEventType
from app.domain.onboarding.entities import OnboardingSession
from app.domain.onboarding.enums import MessageRole, SessionState
from app.domain.onboarding.exceptions import StaleRevisionError
from app.infrastructure.cache.session_cache import SessionCache
from app.infrastructure.db.repositories import PgSessionRepository


@pytest.fixture
def cache(redis_client) -> SessionCache:
    return SessionCache(client=redis_client)


@pytest.fixture
def repo(db_session, cache: SessionCache) -> PgSessionRepository:
    return PgSessionRepository(db=db_session, cache=cache)


class TestRoundTrip:
    async def test_add_then_get_returns_equivalent_session(
        self, repo: PgSessionRepository, db_session
    ) -> None:
        s = OnboardingSession.create(user_id=uuid4())
        s.append_message(role=MessageRole.ASSISTANT, content="hi")
        await repo.add(s)
        await db_session.commit()

        loaded = await repo.get(s.id)
        assert loaded is not None
        assert loaded.id == s.id
        assert loaded.user_id == s.user_id
        assert loaded.state == SessionState.NEW
        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "hi"

    async def test_get_unknown_returns_none(self, repo: PgSessionRepository) -> None:
        assert await repo.get(uuid4()) is None


class TestSaveAndOptimisticConcurrency:
    async def test_save_persists_new_messages(
        self, repo: PgSessionRepository, db_session
    ) -> None:
        s = OnboardingSession.create(user_id=uuid4())
        await repo.add(s)
        await db_session.commit()

        expected_rev = s.revision
        s.append_message(role=MessageRole.USER, content="oi")
        s.append_message(role=MessageRole.ASSISTANT, content="oi de volta")
        await repo.save(s, expected_revision=expected_rev)
        await db_session.commit()

        loaded = await repo.get(s.id)
        assert loaded is not None
        assert len(loaded.messages) == 2
        assert loaded.state == SessionState.IN_PROGRESS

    async def test_stale_revision_raises(
        self, repo: PgSessionRepository, db_session
    ) -> None:
        s = OnboardingSession.create(user_id=uuid4())
        await repo.add(s)
        await db_session.commit()
        s.append_message(role=MessageRole.USER, content="oi")
        await repo.save(s, expected_revision=0)
        await db_session.commit()

        # Second save with the now-stale expected_revision should fail.
        with pytest.raises(StaleRevisionError):
            await repo.save(s, expected_revision=0)


class TestDomainEventsOutbox:
    async def test_events_are_persisted(
        self, repo: PgSessionRepository, db_session
    ) -> None:
        s = OnboardingSession.create(user_id=uuid4())
        evt = DomainEvent.for_session(
            session_id=s.id, event_type=SessionEventType.STARTED
        )
        await repo.add(s, events=[evt])
        await db_session.commit()

        from sqlalchemy import select

        from app.infrastructure.db.models import DomainEventModel

        rows = (
            await db_session.execute(
                select(DomainEventModel).where(DomainEventModel.aggregate_id == s.id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].event_type == SessionEventType.STARTED
        assert rows[0].published_at is None


class TestCacheBehaviour:
    async def test_cache_hit_avoids_db(
        self, repo: PgSessionRepository, cache: SessionCache, db_session
    ) -> None:
        s = OnboardingSession.create(user_id=uuid4())
        await repo.add(s)
        await db_session.commit()

        # Confirm it's in the cache after add().
        cached = await cache.get(s.id)
        assert cached is not None
        assert cached.id == s.id

    async def test_cache_invalidated_on_stale_save(
        self, repo: PgSessionRepository, cache: SessionCache, db_session
    ) -> None:
        s = OnboardingSession.create(user_id=uuid4())
        await repo.add(s)
        await db_session.commit()

        s.append_message(role=MessageRole.USER, content="oi")
        with pytest.raises(StaleRevisionError):
            await repo.save(s, expected_revision=99)  # bogus

        assert await cache.get(s.id) is None