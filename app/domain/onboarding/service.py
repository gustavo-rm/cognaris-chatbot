"""Onboarding application service.

Coordinates the SessionRepository, generates domain events, and exposes a
clean API surface to the HTTP layer.

In Phase 2 the assistant reply is a placeholder ('echo'). Phase 4 will replace
this method's body with a call to the workflow orchestrator.
"""
from __future__ import annotations

from uuid import UUID

from app.core.logging import get_logger
from app.domain.events import DomainEvent, SessionEventType
from app.domain.onboarding.entities import OnboardingSession
from app.domain.onboarding.enums import (
    ClientPlatform,
    MessageRole,
    SessionState,
)
from app.domain.onboarding.exceptions import (
    SessionExpiredError,
    SessionNotFoundError,
)
from app.domain.onboarding.repository import SessionRepository

logger = get_logger(__name__)

# Placeholder replies — replaced by the workflow engine in Phase 4.
_GREETING = (
    "Oi! Eu sou o assistente que vai montar seu plano de estudos personalizado. "
    "Por enquanto sou apenas um eco; em breve farei perguntas reais sobre você."
)
_ECHO_PREFIX = "Recebi sua mensagem: "


class OnboardingService:
    def __init__(self, *, repo: SessionRepository) -> None:
        self._repo = repo

    # ----------- Commands -----------

    async def start_session(
        self,
        *,
        user_id: UUID,
        locale: str = "pt-BR",
        client_platform: ClientPlatform = ClientPlatform.WEB,
    ) -> OnboardingSession:
        session = OnboardingSession.create(
            user_id=user_id,
            locale=locale,
            client_platform=client_platform,
        )

        # First assistant turn is the greeting. Append it directly; no state
        # transition (session stays NEW until the user replies).
        session.append_message(role=MessageRole.ASSISTANT, content=_GREETING)

        event = DomainEvent.for_session(
            session_id=session.id,
            event_type=SessionEventType.STARTED,
            payload={"user_id": str(user_id), "locale": locale},
        )

        await self._repo.add(session, events=[event])
        logger.info(
            "session.started",
            session_id=str(session.id),
            user_id=str(user_id),
            locale=locale,
        )
        return session

    async def get_session(self, session_id: UUID) -> OnboardingSession:
        session = await self._repo.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                f"Session {session_id} not found",
                details={"session_id": str(session_id)},
            )
        return session

    async def handle_user_message(
        self,
        *,
        session_id: UUID,
        content: str,
        rich_payload: dict | None = None,
    ) -> tuple[OnboardingSession, "ConversationMessage", "ConversationMessage"]:  # noqa: F821
        """Append the user's message and produce a (placeholder) assistant reply.

        Phase 4 will replace the body of this method with a call to the workflow
        orchestrator. The public signature must remain stable.
        """
        session = await self.get_session(session_id)
        expected_revision = session.revision

        if session.is_expired:
            raise SessionExpiredError(
                "Session has expired",
                details={"expires_at": session.expires_at.isoformat()},
            )

        user_msg = session.append_message(
            role=MessageRole.USER,
            content=content,
            rich_payload=rich_payload,
        )

        # Placeholder assistant logic — Phase 4 replaces this.
        assistant_text = _ECHO_PREFIX + content
        assistant_msg = session.append_message(
            role=MessageRole.ASSISTANT,
            content=assistant_text,
        )

        events = [
            DomainEvent.for_session(
                session_id=session.id,
                event_type=SessionEventType.MESSAGE_APPENDED,
                payload={"role": "user", "sequence": user_msg.sequence},
            ),
            DomainEvent.for_session(
                session_id=session.id,
                event_type=SessionEventType.MESSAGE_APPENDED,
                payload={"role": "assistant", "sequence": assistant_msg.sequence},
            ),
        ]

        await self._repo.save(
            session, expected_revision=expected_revision, events=events
        )

        logger.info(
            "session.message_handled",
            session_id=str(session.id),
            state=session.state.value,
            revision=session.revision,
        )
        return session, user_msg, assistant_msg

    async def transition(
        self, *, session_id: UUID, target: SessionState
    ) -> OnboardingSession:
        """Move a session to a target state. Used by tests and admin tools.

        Phase 6+ will use this from the workflow engine and finalize logic.
        """
        session = await self.get_session(session_id)
        expected_revision = session.revision
        previous = session.state
        session.transition_to(target)

        event = DomainEvent.for_session(
            session_id=session.id,
            event_type=SessionEventType.STATE_CHANGED,
            payload={"from": previous.value, "to": target.value},
        )
        await self._repo.save(
            session, expected_revision=expected_revision, events=[event]
        )
        return session