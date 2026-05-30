"""ORM model for ConversationMessage."""
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.onboarding.enums import MessageRole
from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin

message_role_enum = PG_ENUM(
    MessageRole,
    name="message_role",
    values_callable=lambda x: [e.value for e in x],
    create_type=False,
)


class ConversationMessageModel(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "sequence", name="uq_conversation_messages_session_sequence"
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(message_role_enum, nullable=False)
    content: Mapped[str] = mapped_column(String(8_000), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    rich_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["OnboardingSessionModel"] = relationship(  # noqa: F821
        back_populates="messages"
    )