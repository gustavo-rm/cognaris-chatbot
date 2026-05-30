"""Onboarding-specific exceptions.

All extend DomainError so they translate to HTTP responses automatically via the
handlers registered in api/errors.py.
"""
from typing import Any

from app.core.exceptions import ConflictError, NotFoundError, ValidationError


class SessionNotFoundError(NotFoundError):
    code = "SESSION_NOT_FOUND"


class SessionAlreadyExistsError(ConflictError):
    code = "SESSION_ALREADY_EXISTS"


class InvalidSessionStateError(ConflictError):
    code = "INVALID_SESSION_STATE"


class StaleRevisionError(ConflictError):
    """Raised when an optimistic-concurrency check fails."""

    code = "STALE_REVISION"

    def __init__(self, *, expected: int, actual: int) -> None:
        super().__init__(
            f"Stale revision: expected {expected}, got {actual}",
            details={"expected": expected, "actual": actual},
        )


class SessionExpiredError(ConflictError):
    code = "SESSION_EXPIRED"


class InvalidMessageError(ValidationError):
    code = "INVALID_MESSAGE"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)