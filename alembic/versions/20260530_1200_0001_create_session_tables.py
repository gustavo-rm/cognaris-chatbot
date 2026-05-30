"""create session, message, and domain_event tables

Revision ID: 0001
Revises:
Create Date: 2026-05-25 12:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


SESSION_STATE_VALUES = (
    "new",
    "in_progress",
    "awaiting_confirmation",
    "submitted",
    "completed",
    "paused",
    "abandoned",
    "archived",
    "failed",
)
CLIENT_PLATFORM_VALUES = ("web", "mobile_ios", "mobile_android", "whatsapp", "unknown")
MESSAGE_ROLE_VALUES = ("user", "assistant", "system")


def upgrade() -> None:
    session_state = postgresql.ENUM(
        *SESSION_STATE_VALUES, name="session_state", create_type=True
    )
    client_platform = postgresql.ENUM(
        *CLIENT_PLATFORM_VALUES, name="client_platform", create_type=True
    )
    message_role = postgresql.ENUM(
        *MESSAGE_ROLE_VALUES, name="message_role", create_type=True
    )

    bind = op.get_bind()
    session_state.create(bind, checkfirst=True)
    client_platform.create(bind, checkfirst=True)
    message_role.create(bind, checkfirst=True)

    op.create_table(
        "onboarding_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "state",
            postgresql.ENUM(*SESSION_STATE_VALUES, name="session_state", create_type=False),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locale", sa.String(length=10), nullable=False, server_default="pt-BR"),
        sa.Column(
            "client_platform",
            postgresql.ENUM(
                *CLIENT_PLATFORM_VALUES, name="client_platform", create_type=False
            ),
            nullable=False,
            server_default="web",
        ),
        sa.Column("current_step", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_onboarding_sessions_user_id", "onboarding_sessions", ["user_id"])
    op.create_index("ix_onboarding_sessions_state", "onboarding_sessions", ["state"])
    op.create_index(
        "ix_onboarding_sessions_last_active_at", "onboarding_sessions", ["last_active_at"]
    )
    op.create_index(
        "ix_onboarding_sessions_expires_at", "onboarding_sessions", ["expires_at"]
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM(*MESSAGE_ROLE_VALUES, name="message_role", create_type=False),
            nullable=False,
        ),
        sa.Column("content", sa.String(length=8_000), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("rich_payload", postgresql.JSONB(), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "sequence", name="uq_conversation_messages_session_sequence"
        ),
    )
    op.create_index(
        "ix_conversation_messages_session_id", "conversation_messages", ["session_id"]
    )

    op.create_table(
        "domain_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_domain_events_aggregate_id", "domain_events", ["aggregate_id"])
    op.create_index("ix_domain_events_event_type", "domain_events", ["event_type"])
    op.create_index("ix_domain_events_occurred_at", "domain_events", ["occurred_at"])
    op.create_index("ix_domain_events_published_at", "domain_events", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_domain_events_published_at", table_name="domain_events")
    op.drop_index("ix_domain_events_occurred_at", table_name="domain_events")
    op.drop_index("ix_domain_events_event_type", table_name="domain_events")
    op.drop_index("ix_domain_events_aggregate_id", table_name="domain_events")
    op.drop_table("domain_events")

    op.drop_index(
        "ix_conversation_messages_session_id", table_name="conversation_messages"
    )
    op.drop_table("conversation_messages")

    op.drop_index(
        "ix_onboarding_sessions_expires_at", table_name="onboarding_sessions"
    )
    op.drop_index(
        "ix_onboarding_sessions_last_active_at", table_name="onboarding_sessions"
    )
    op.drop_index("ix_onboarding_sessions_state", table_name="onboarding_sessions")
    op.drop_index("ix_onboarding_sessions_user_id", table_name="onboarding_sessions")
    op.drop_table("onboarding_sessions")

    bind = op.get_bind()
    postgresql.ENUM(name="message_role").drop(bind, checkfirst=True)
    postgresql.ENUM(name="client_platform").drop(bind, checkfirst=True)
    postgresql.ENUM(name="session_state").drop(bind, checkfirst=True)