"""Domain events.

These are persisted in the same DB transaction as state changes (outbox pattern).
A future worker (Phase 7) will publish them to the event bus and mark them
delivered. For now we just write them and never read — the contract is what
matters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.ids import new_id
from app.core.time import utcnow


@dataclass(frozen=True)
class DomainEvent:
    id: UUID
    aggregate_id: UUID
    aggregate_type: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime

    @classmethod
    def for_session(
        cls,
        *,
        session_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> DomainEvent:
        return cls(
            id=new_id(),
            aggregate_id=session_id,
            aggregate_type="onboarding_session",
            event_type=event_type,
            payload=payload or {},
            occurred_at=utcnow(),
        )


# Canonical event type strings — keep in sync with consumers.
class SessionEventType:
    STARTED = "session.started"
    MESSAGE_APPENDED = "session.message_appended"
    STATE_CHANGED = "session.state_changed"
    SUBMITTED = "session.submitted"
    COMPLETED = "session.completed"
    EXPIRED = "session.expired"