"""Domain exceptions.

These are framework-agnostic. The API layer translates them into HTTP responses
in app/api/errors.py — never raise HTTPException from domain code.
"""
from typing import Any


class DomainError(Exception):
    """Base class for all expected domain-level errors."""

    code: str = "DOMAIN_ERROR"
    http_status: int = 400

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class ConflictError(DomainError):
    code = "CONFLICT"
    http_status = 409


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    http_status = 422


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"
    http_status = 401


class DependencyUnavailableError(DomainError):
    """Raised when an external dependency (DB, Redis, LLM, etc.) is unreachable."""

    code = "DEPENDENCY_UNAVAILABLE"
    http_status = 503