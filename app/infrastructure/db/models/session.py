"""ORM model for OnboardingSession."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.onboarding.enums import ClientPlatform, SessionState
from app.infrastructure.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Postgres native enums — created via Alembic in the migration below.
session_state_enum = PG_ENUM(
    SessionState,
    name="session_state",
    values_callable=lambda x: [e.value for e in x],
    create_type=False,
)
client_platform_enum = PG_ENUM(
    ClientPlatform,
    name="client_platform",
    values_callable=lambda x: [e.value for e in x],
    create_type=False,
)


class OnboardingSessionModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "onboarding_sessions"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    state: Mapped[SessionState] = mapped_column(session_state_enum, nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="pt-BR")
    client_platform: Mapped[ClientPlatform] = mapped_column(
        client_platform_enum, nullable=False, default=ClientPlatform.WEB
    )
    current_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["ConversationMessageModel"]] = relationship(  # noqa: F821
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessageModel.sequence",
        lazy="selectin",
    )