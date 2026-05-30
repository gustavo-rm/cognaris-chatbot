"""Concrete SessionRepository: Postgres + Redis cache-aside."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.domain.events import DomainEvent
from app.domain.onboarding.entities import ConversationMessage, OnboardingSession
from app.domain.onboarding.enums import ClientPlatform, MessageRole, SessionState
from app.domain.onboarding.exceptions import (
    SessionAlreadyExistsError,
    StaleRevisionError,
)
from app.infrastructure.cache.session_cache import SessionCache
from app.infrastructure.db.models import (
    ConversationMessageModel,
    DomainEventModel,
    OnboardingSessionModel,
)

logger = get_logger(__name__)


class PgSessionRepository:
    """SessionRepository backed by Postgres with Redis cache-aside."""

    def __init__(self, *, db: AsyncSession, cache: SessionCache) -> None:
        self._db = db
        self._cache = cache

    # ----------- Public API -----------

    async def add(
        self,
        session: OnboardingSession,
        *,
        events: list[DomainEvent] | None = None,
    ) -> None:
        model = _entity_to_model(session)
        self._db.add(model)
        for msg in session.messages:
            self._db.add(_message_entity_to_model(msg))
        for evt in events or []:
            self._db.add(_event_to_model(evt))

        try:
            await self._db.flush()
        except Exception as exc:  # pragma: no cover - mapped below
            # Unique constraint on id (UUID collision is astronomically rare,
            # but handle deterministically).
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                raise SessionAlreadyExistsError(
                    f"Session {session.id} already exists",
                    details={"session_id": str(session.id)},
                ) from exc
            raise

        # Write-through cache.
        await self._cache.set(session)

    async def get(self, session_id: UUID) -> OnboardingSession | None:
        cached = await self._cache.get(session_id)
        if cached is not None:
            return cached

        stmt = (
            select(OnboardingSessionModel)
            .where(OnboardingSessionModel.id == session_id)
            .options(selectinload(OnboardingSessionModel.messages))
        )
        model = (await self._db.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None

        entity = _model_to_entity(model)
        await self._cache.set(entity)
        return entity

    async def save(
        self,
        session: OnboardingSession,
        *,
        expected_revision: int,
        events: list[DomainEvent] | None = None,
    ) -> None:
        # Optimistic concurrency: update only if DB revision matches expected.
        existing_stmt = select(OnboardingSessionModel).where(
            OnboardingSessionModel.id == session.id
        )
        existing = (await self._db.execute(existing_stmt)).scalar_one_or_none()
        if existing is None:
            raise StaleRevisionError(expected=expected_revision, actual=-1)
        if existing.revision != expected_revision:
            # Cache may have been stale; invalidate so the next read goes to DB.
            await self._cache.invalidate(session.id)
            raise StaleRevisionError(
                expected=expected_revision, actual=existing.revision
            )

        # Apply updates to the loaded model (avoids a full re-merge round-trip).
        _apply_entity_to_model(session, existing)

        # Persist only NEW messages (sequence >= existing message count).
        # We compute "existing message count" from the DB to be safe under
        # concurrent appends — though optimistic concurrency above should
        # already have caught those.
        from sqlalchemy import func

        max_seq_stmt = select(
            func.coalesce(func.max(ConversationMessageModel.sequence), -1)
        ).where(ConversationMessageModel.session_id == session.id)
        max_seq = (await self._db.execute(max_seq_stmt)).scalar_one()

        for msg in session.messages:
            if msg.sequence > max_seq:
                self._db.add(_message_entity_to_model(msg))

        for evt in events or []:
            self._db.add(_event_to_model(evt))

        await self._db.flush()
        await self._cache.set(session)


# --------- Mapping helpers ---------


def _entity_to_model(s: OnboardingSession) -> OnboardingSessionModel:
    return OnboardingSessionModel(
        id=s.id,
        user_id=s.user_id,
        state=s.state,
        revision=s.revision,
        locale=s.locale,
        client_platform=s.client_platform,
        current_step=s.current_step,
        started_at=s.started_at,
        last_active_at=s.last_active_at,
        expires_at=s.expires_at,
        confirmed_at=s.confirmed_at,
        submitted_at=s.submitted_at,
        completed_at=s.completed_at,
    )


def _apply_entity_to_model(s: OnboardingSession, m: OnboardingSessionModel) -> None:
    m.state = s.state
    m.revision = s.revision
    m.current_step = s.current_step
    m.last_active_at = s.last_active_at
    m.expires_at = s.expires_at
    m.confirmed_at = s.confirmed_at
    m.submitted_at = s.submitted_at
    m.completed_at = s.completed_at


def _message_entity_to_model(msg: ConversationMessage) -> ConversationMessageModel:
    return ConversationMessageModel(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        sequence=msg.sequence,
        rich_payload=msg.rich_payload,
        extra_metadata=msg.metadata,
        created_at=msg.created_at,
    )


def _event_to_model(evt: DomainEvent) -> DomainEventModel:
    return DomainEventModel(
        id=evt.id,
        aggregate_id=evt.aggregate_id,
        aggregate_type=evt.aggregate_type,
        event_type=evt.event_type,
        payload=evt.payload,
        occurred_at=evt.occurred_at,
    )


def _model_to_entity(m: OnboardingSessionModel) -> OnboardingSession:
    messages = [
        ConversationMessage(
            id=msg.id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            sequence=msg.sequence,
            created_at=msg.created_at,
            rich_payload=msg.rich_payload,
            metadata=msg.extra_metadata,
        )
        for msg in m.messages
    ]
    return OnboardingSession(
        id=m.id,
        user_id=m.user_id,
        state=m.state,
        revision=m.revision,
        locale=m.locale,
        client_platform=m.client_platform,
        current_step=m.current_step,
        started_at=m.started_at,
        last_active_at=m.last_active_at,
        expires_at=m.expires_at,
        confirmed_at=m.confirmed_at,
        submitted_at=m.submitted_at,
        completed_at=m.completed_at,
        messages=messages,
    )