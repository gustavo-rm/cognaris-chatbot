"""API DTOs (Pydantic) for onboarding endpoints.

These are NOT domain entities. They live at the API boundary and exist to
decouple wire format from internal model. Mapping happens in the service layer.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.onboarding.enums import ClientPlatform, MessageRole, SessionState


class StartSessionRequest(BaseModel):
    user_id: UUID
    locale: str = Field(default="pt-BR", max_length=10)
    client_platform: ClientPlatform = ClientPlatform.WEB


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8_000)
    rich_payload: dict[str, Any] | None = None


class ConversationMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: MessageRole
    content: str
    sequence: int
    created_at: datetime
    rich_payload: dict[str, Any] | None = None


class SessionSummaryOut(BaseModel):
    """Compact session view returned by GET /sessions/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    state: SessionState
    revision: int
    locale: str
    client_platform: ClientPlatform
    current_step: str | None
    started_at: datetime
    last_active_at: datetime
    expires_at: datetime
    is_expired: bool
    message_count: int


class SessionDetailOut(SessionSummaryOut):
    """Full session view including message history."""

    messages: list[ConversationMessageOut]


class SendMessageResponse(BaseModel):
    session: SessionSummaryOut
    user_message: ConversationMessageOut
    assistant_message: ConversationMessageOut