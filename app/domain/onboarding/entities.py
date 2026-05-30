"""Onboarding domain entities.

These are pure Python classes — no ORM, no serialization framework. They model
the business rules (valid state transitions, message immutability, revision
bumping) without leaking infrastructure concerns.

The ORM models in infrastructure/db/models/ are translated to/from these via
the SessionRepository.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.ids import new_id
from app.core.time import utcnow
from app.domain.onboarding.enums import (
    INTERACTIVE_STATES,
    TERMINAL_STATES,
    ClientPlatform,
    MessageRole,
    SessionState,
)
from app.domain.onboarding.exceptions import (
    InvalidMessageError,
    InvalidSessionStateError,
    SessionExpiredError,
)

# Allowed state transitions. Anything not listed here raises InvalidSessionStateError.
_ALLOWED_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.NEW: frozenset({SessionState.IN_PROGRESS, SessionState.ABANDONED}),
    SessionState.IN_PROGRESS: frozenset(
        {
            SessionState.IN_PROGRESS,  # allow self for revision-bumping appends
            SessionState.AWAITING_CONFIRMATION,
            SessionState.PAUSED,
            SessionState.ABANDONED,
            SessionState.FAILED,
        }
    ),
    SessionState.AWAITING_CONFIRMATION: frozenset(
        {
            SessionState.IN_PROGRESS,  # user wants to edit
            SessionState.SUBMITTED,
            SessionState.PAUSED,
            SessionState.ABANDONED,
            SessionState.FAILED,
        }
    ),
    SessionState.SUBMITTED: frozenset({SessionState.COMPLETED, SessionState.FAILED}),
    SessionState.PAUSED: frozenset(
        {SessionState.IN_PROGRESS, SessionState.ABANDONED}
    ),
    SessionState.ABANDONED: frozenset({SessionState.ARCHIVED}),
    # Terminals can't transition out.
    SessionState.COMPLETED: frozenset(),
    SessionState.ARCHIVED: frozenset(),
    SessionState.FAILED: frozenset(),
}


@dataclass(frozen=True)
class ConversationMessage:
    """An immutable conversation turn.

    Frozen dataclass: once created, fields can't be reassigned. The append-only
    log property is enforced at the type level.
    """

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    sequence: int  # monotonic per-session ordering
    created_at: datetime
    rich_payload: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.content and not self.rich_payload:
            raise InvalidMessageError(
                "Message must have content or rich_payload",
                details={"role": self.role.value},
            )
        if len(self.content) > 8_000:
            raise InvalidMessageError(
                "Message content exceeds 8000 chars",
                details={"length": len(self.content)},
            )


@dataclass
class OnboardingSession:
    """Aggregate root for the onboarding flow.

    Business invariants enforced here:
    - state transitions follow the allowed graph,
    - revision is bumped on every mutation,
    - messages are append-only and have monotonic sequence numbers,
    - last_active_at moves forward only,
    - terminal states reject all mutations.
    """

    id: UUID
    user_id: UUID
    state: SessionState
    revision: int
    locale: str
    client_platform: ClientPlatform
    started_at: datetime
    last_active_at: datetime
    expires_at: datetime
    current_step: str | None = None
    confirmed_at: datetime | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    messages: list[ConversationMessage] = field(default_factory=list)

    # Sliding TTL bumps the deadline this far on every interaction.
    _ttl: timedelta = field(default_factory=lambda: timedelta(hours=24))

    # ------------- Factory -------------

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        locale: str = "pt-BR",
        client_platform: ClientPlatform = ClientPlatform.WEB,
        ttl: timedelta = timedelta(hours=24),
    ) -> OnboardingSession:
        now = utcnow()
        return cls(
            id=new_id(),
            user_id=user_id,
            state=SessionState.NEW,
            revision=0,
            locale=locale,
            client_platform=client_platform,
            started_at=now,
            last_active_at=now,
            expires_at=now + ttl,
            _ttl=ttl,
        )

    # ------------- Queries -------------

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_interactive(self) -> bool:
        return self.state in INTERACTIVE_STATES

    @property
    def is_expired(self) -> bool:
        return utcnow() >= self.expires_at

    @property
    def next_message_sequence(self) -> int:
        return len(self.messages)

    # ------------- Commands -------------

    def transition_to(self, target: SessionState) -> None:
        """Move the session to a new state, validating the transition.

        Raises InvalidSessionStateError if the transition is not allowed.
        """
        if self.is_terminal:
            raise InvalidSessionStateError(
                f"Session is in terminal state {self.state.value}",
                details={"current_state": self.state.value},
            )

        allowed = _ALLOWED_TRANSITIONS.get(self.state, frozenset())
        if target not in allowed:
            raise InvalidSessionStateError(
                f"Cannot transition from {self.state.value} to {target.value}",
                details={
                    "current_state": self.state.value,
                    "target_state": target.value,
                    "allowed": [s.value for s in allowed],
                },
            )

        # Record timestamps tied to specific transitions.
        now = utcnow()
        if target == SessionState.AWAITING_CONFIRMATION:
            self.confirmed_at = now
        elif target == SessionState.SUBMITTED:
            self.submitted_at = now
        elif target == SessionState.COMPLETED:
            self.completed_at = now

        self.state = target
        self._bump_activity()

    def append_message(
        self,
        *,
        role: MessageRole,
        content: str,
        rich_payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationMessage:
        """Append a message and bump the session revision.

        Auto-transitions NEW → IN_PROGRESS when the first user message arrives.
        Rejects messages when the session is terminal or expired.
        """
        if self.is_terminal:
            raise InvalidSessionStateError(
                f"Cannot append message: session is {self.state.value}",
                details={"current_state": self.state.value},
            )
        if self.is_expired:
            raise SessionExpiredError(
                "Session has expired",
                details={"expires_at": self.expires_at.isoformat()},
            )

        # First user message auto-advances NEW → IN_PROGRESS.
        if self.state == SessionState.NEW and role == MessageRole.USER:
            self.transition_to(SessionState.IN_PROGRESS)

        message = ConversationMessage(
            id=new_id(),
            session_id=self.id,
            role=role,
            content=content,
            sequence=self.next_message_sequence,
            created_at=utcnow(),
            rich_payload=rich_payload,
            metadata=metadata,
        )
        self.messages.append(message)
        self._bump_activity()
        return message

    def update_current_step(self, step: str | None) -> None:
        """Phase 4 will use this when the workflow advances."""
        if self.is_terminal:
            raise InvalidSessionStateError(
                f"Cannot update step: session is {self.state.value}"
            )
        self.current_step = step
        self._bump_activity()

    def extend_ttl(self) -> None:
        """Slide the expiration window forward."""
        if self.is_terminal:
            return
        self.expires_at = utcnow() + self._ttl
        self._bump_activity()

    # ------------- Internals -------------

    def _bump_activity(self) -> None:
        self.last_active_at = utcnow()
        self.revision += 1
        if not self.is_terminal:
            self.expires_at = self.last_active_at + self._ttl