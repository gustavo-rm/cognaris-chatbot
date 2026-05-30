"""Enums for the onboarding aggregate.

These live in domain/ because they're part of the ubiquitous language and are
referenced by both the API DTOs and the ORM models. Keeping them framework-free
means the API can serialize them, the DB can persist them, and tests can compare
them — without any of those layers depending on the others.
"""
from enum import StrEnum


class SessionState(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"
    ARCHIVED = "archived"
    FAILED = "failed"


# Terminal states: no further transitions allowed.
TERMINAL_STATES = frozenset(
    {SessionState.COMPLETED, SessionState.ARCHIVED, SessionState.FAILED}
)

# States that allow user interaction.
INTERACTIVE_STATES = frozenset(
    {SessionState.NEW, SessionState.IN_PROGRESS, SessionState.AWAITING_CONFIRMATION}
)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ClientPlatform(StrEnum):
    WEB = "web"
    MOBILE_IOS = "mobile_ios"
    MOBILE_ANDROID = "mobile_android"
    WHATSAPP = "whatsapp"
    UNKNOWN = "unknown"