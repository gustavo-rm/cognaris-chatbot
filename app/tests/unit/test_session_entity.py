"""Unit tests for the OnboardingSession aggregate.

These exercise pure domain logic — no DB, no Redis, no FastAPI.
"""
from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.time import utcnow
from app.domain.onboarding.entities import OnboardingSession
from app.domain.onboarding.enums import ClientPlatform, MessageRole, SessionState
from app.domain.onboarding.exceptions import (
    InvalidMessageError,
    InvalidSessionStateError,
    SessionExpiredError,
)


def _make_session() -> OnboardingSession:
    return OnboardingSession.create(
        user_id=uuid4(), client_platform=ClientPlatform.WEB
    )


class TestSessionCreation:
    def test_new_session_starts_in_NEW_state(self) -> None:
        s = _make_session()
        assert s.state == SessionState.NEW
        assert s.revision == 0
        assert s.messages == []
        assert s.is_interactive is True
        assert s.is_terminal is False

    def test_expires_in_24h_by_default(self) -> None:
        s = _make_session()
        delta = s.expires_at - s.started_at
        assert delta == timedelta(hours=24)


class TestMessageAppending:
    def test_appending_user_message_auto_transitions_to_in_progress(self) -> None:
        s = _make_session()
        msg = s.append_message(role=MessageRole.USER, content="oi")
        assert s.state == SessionState.IN_PROGRESS
        assert msg.sequence == 0
        assert s.revision >= 1

    def test_appending_assistant_message_does_not_transition(self) -> None:
        s = _make_session()
        s.append_message(role=MessageRole.ASSISTANT, content="hello")
        assert s.state == SessionState.NEW

    def test_messages_have_monotonic_sequence(self) -> None:
        s = _make_session()
        m1 = s.append_message(role=MessageRole.ASSISTANT, content="a")
        m2 = s.append_message(role=MessageRole.USER, content="b")
        m3 = s.append_message(role=MessageRole.ASSISTANT, content="c")
        assert (m1.sequence, m2.sequence, m3.sequence) == (0, 1, 2)

    def test_empty_message_is_rejected(self) -> None:
        s = _make_session()
        with pytest.raises(InvalidMessageError):
            s.append_message(role=MessageRole.USER, content="")

    def test_message_too_long_is_rejected(self) -> None:
        s = _make_session()
        with pytest.raises(InvalidMessageError):
            s.append_message(role=MessageRole.USER, content="x" * 8_001)

    def test_cannot_append_when_terminal(self) -> None:
        s = _make_session()
        s.append_message(role=MessageRole.USER, content="hi")
        s.transition_to(SessionState.AWAITING_CONFIRMATION)
        s.transition_to(SessionState.SUBMITTED)
        s.transition_to(SessionState.COMPLETED)
        with pytest.raises(InvalidSessionStateError):
            s.append_message(role=MessageRole.USER, content="too late")

    def test_cannot_append_when_expired(self) -> None:
        s = _make_session()
        s.expires_at = utcnow() - timedelta(seconds=1)
        with pytest.raises(SessionExpiredError):
            s.append_message(role=MessageRole.USER, content="hi")


class TestStateTransitions:
    def test_full_happy_path(self) -> None:
        s = _make_session()
        s.append_message(role=MessageRole.USER, content="hi")  # NEW → IN_PROGRESS
        s.transition_to(SessionState.AWAITING_CONFIRMATION)
        s.transition_to(SessionState.SUBMITTED)
        s.transition_to(SessionState.COMPLETED)
        assert s.is_terminal
        assert s.completed_at is not None
        assert s.submitted_at is not None

    def test_invalid_transition_raises(self) -> None:
        s = _make_session()
        with pytest.raises(InvalidSessionStateError):
            s.transition_to(SessionState.COMPLETED)

    def test_terminal_state_rejects_further_transitions(self) -> None:
        s = _make_session()
        s.append_message(role=MessageRole.USER, content="hi")
        s.transition_to(SessionState.ABANDONED)
        s.transition_to(SessionState.ARCHIVED)
        with pytest.raises(InvalidSessionStateError):
            s.transition_to(SessionState.IN_PROGRESS)

    def test_can_go_back_from_awaiting_to_in_progress(self) -> None:
        """User can choose to edit answers after reaching the review step."""
        s = _make_session()
        s.append_message(role=MessageRole.USER, content="hi")
        s.transition_to(SessionState.AWAITING_CONFIRMATION)
        s.transition_to(SessionState.IN_PROGRESS)
        assert s.state == SessionState.IN_PROGRESS


class TestRevisionAndActivity:
    def test_revision_increments_on_every_mutation(self) -> None:
        s = _make_session()
        r0 = s.revision
        s.append_message(role=MessageRole.USER, content="a")
        assert s.revision > r0
        r1 = s.revision
        s.transition_to(SessionState.AWAITING_CONFIRMATION)
        assert s.revision > r1

    def test_extend_ttl_slides_expiration_forward(self) -> None:
        s = _make_session()
        original_expiry = s.expires_at
        # Force a small backwards adjustment so the test isn't flaky on fast machines.
        s.expires_at = original_expiry - timedelta(minutes=5)
        s.extend_ttl()
        assert s.expires_at > original_expiry - timedelta(minutes=1)