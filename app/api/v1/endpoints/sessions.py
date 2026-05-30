"""Onboarding session endpoints.

Phase 2 surface area:
- POST /sessions                       — create a new session
- GET  /sessions/{id}                  — retrieve full session with messages
- POST /sessions/{id}/messages         — send a user message, get assistant reply
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_dep, redis_dep
from app.domain.onboarding.entities import ConversationMessage, OnboardingSession
from app.domain.onboarding.repository import SessionRepository
from app.domain.onboarding.schemas import (
    ConversationMessageOut,
    SendMessageRequest,
    SendMessageResponse,
    SessionDetailOut,
    SessionSummaryOut,
    StartSessionRequest,
)
from app.domain.onboarding.service import OnboardingService
from app.infrastructure.cache.session_cache import SessionCache
from app.infrastructure.db.repositories import PgSessionRepository

router = APIRouter(tags=["onboarding"])


def _service(db: AsyncSession, redis_client) -> OnboardingService:
    cache = SessionCache(client=redis_client)
    repo: SessionRepository = PgSessionRepository(db=db, cache=cache)
    return OnboardingService(repo=repo)


def _to_summary(session: OnboardingSession) -> SessionSummaryOut:
    return SessionSummaryOut(
        id=session.id,
        user_id=session.user_id,
        state=session.state,
        revision=session.revision,
        locale=session.locale,
        client_platform=session.client_platform,
        current_step=session.current_step,
        started_at=session.started_at,
        last_active_at=session.last_active_at,
        expires_at=session.expires_at,
        is_expired=session.is_expired,
        message_count=len(session.messages),
    )


def _to_message_out(msg: ConversationMessage) -> ConversationMessageOut:
    return ConversationMessageOut(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        sequence=msg.sequence,
        created_at=msg.created_at,
        rich_payload=msg.rich_payload,
    )


@router.post(
    "/sessions",
    response_model=SessionDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(
    body: StartSessionRequest,
    db: AsyncSession = Depends(db_session_dep),
    redis_client=Depends(redis_dep),
) -> SessionDetailOut:
    service = _service(db, redis_client)
    session = await service.start_session(
        user_id=body.user_id,
        locale=body.locale,
        client_platform=body.client_platform,
    )
    return SessionDetailOut(
        **_to_summary(session).model_dump(),
        messages=[_to_message_out(m) for m in session.messages],
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(db_session_dep),
    redis_client=Depends(redis_dep),
) -> SessionDetailOut:
    service = _service(db, redis_client)
    session = await service.get_session(session_id)
    return SessionDetailOut(
        **_to_summary(session).model_dump(),
        messages=[_to_message_out(m) for m in session.messages],
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def send_message(
    session_id: UUID,
    body: SendMessageRequest,
    db: AsyncSession = Depends(db_session_dep),
    redis_client=Depends(redis_dep),
) -> SendMessageResponse:
    service = _service(db, redis_client)
    session, user_msg, assistant_msg = await service.handle_user_message(
        session_id=session_id,
        content=body.content,
        rich_payload=body.rich_payload,
    )
    return SendMessageResponse(
        session=_to_summary(session),
        user_message=_to_message_out(user_msg),
        assistant_message=_to_message_out(assistant_msg),
    )