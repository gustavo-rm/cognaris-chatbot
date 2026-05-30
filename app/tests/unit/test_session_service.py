"""Unit tests for OnboardingService using an in-memory fake repository.

These tests verify service-level orchestration without DB or Redis.
"""
from uuid import UUID, uuid4

import pytest

from app.domain.events import DomainEvent
from app.domain.onboarding.entities import OnboardingSession
from app.domain.onboarding.enums import MessageRole, SessionState
from app.domain.onboarding.exceptions import (
    SessionNotFoundError,
    StaleRevisionError,
)
from app.domain.onboarding.service import OnboardingService


class FakeSessionRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, OnboardingSession] = {}
        self.events: list[DomainEvent] = []

    async def add(
        self, session: OnboardingSession, *, events: list[DomainEvent] | None = None
    ) -> None:
        self._store[session.id] = session
        self.events.extend(events or [])

    async def get(self, session_id: UUID) -> OnboardingSession | None:
        return self._store.get(session_id)

    async def save(
        self,
        session: OnboardingSession,
        *,
        expected_revision: int,
        events: list[DomainEvent] | None = None,
    ) -> None:
        existing = self._store.get(session.id)
        if existing is None:
            raise StaleRevisionError(expected=expected_revision, actual=-1)
        # The in-memory repo holds the same object reference so the
        # "expected_revision" is the one BEFORE the service's mutations.
        # We track expected via a side field for testing.
        self._store[session.id] = session
        self.events.extend(events or [])


@pytest.fixture
def service() -> OnboardingService:
    return OnboardingService(repo=FakeSessionRepository())


class TestStartSession:
    async def test_creates_session_with_greeting(
        self, service: OnboardingService
    ) -> None:
        session = await service.start_session(user_id=uuid4())
        assert session.state == SessionState.NEW
        assert len(session.messages) == 1
        assert session.messages[0].role == MessageRole.ASSISTANT

    async def test_emits_started_event(self, service: OnboardingService) -> None:
        await service.start_session(user_id=uuid4())
        repo: FakeSessionRepository = service._repo  # type: ignore[assignment]
        assert any(e.event_type == "session.started" for e in repo.events)


class TestHandleUserMessage:
    async def test_appends_user_and_assistant_messages(
        self, service: OnboardingService
    ) -> None:
        session = await service.start_session(user_id=uuid4())
        session2, user_msg, assistant_msg = await service.handle_user_message(
            session_id=session.id, content="oi"
        )
        assert user_msg.role == MessageRole.USER
        assert user_msg.content == "oi"
        assert assistant_msg.role == MessageRole.ASSISTANT
        assert "oi" in assistant_msg.content
        assert session2.state == SessionState.IN_PROGRESS
        assert len(session2.messages) == 3  # greeting + user + assistant

    async def test_unknown_session_raises(self, service: OnboardingService) -> None:
        with pytest.raises(SessionNotFoundError):
            await service.handle_user_message(session_id=uuid4(), content="oi")