"""Repository interface for the OnboardingSession aggregate.

Concrete implementations live in infrastructure/. Service code depends on this
abstraction, not on SQLAlchemy or Redis directly.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.events import DomainEvent
from app.domain.onboarding.entities import OnboardingSession


class SessionRepository(Protocol):
    async def add(
        self, session: OnboardingSession, *, events: list[DomainEvent] | None = None
    ) -> None:
        """Insert a brand-new session. Fails if id already exists."""

    async def get(self, session_id: UUID) -> OnboardingSession | None:
        """Load by id with full message history. Returns None if not found."""

    async def save(
        self,
        session: OnboardingSession,
        *,
        expected_revision: int,
        events: list[DomainEvent] | None = None,
    ) -> None:
        """Persist mutations.

        Performs optimistic concurrency check against `expected_revision`.
        Persists new messages incrementally (only those with sequence >= what's
        in the DB). Emits associated domain events to the outbox table.
        """