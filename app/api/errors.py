"""HTTP error handlers.

Translates DomainError subclasses into RFC 7807 Problem Details responses.
Keeps the rest of the codebase free of HTTPException raises.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import DomainError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _problem_response(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    extra: dict | None = None,
) -> JSONResponse:
    body = {
        "type": f"about:blank/{code.lower()}",
        "title": title,
        "status": status,
        "code": code,
        "detail": detail,
    }
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        logger.info(
            "api.domain_error",
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
        return _problem_response(
            status=exc.http_status,
            code=exc.code,
            title=exc.code.replace("_", " ").title(),
            detail=exc.message,
            extra={"details": exc.details} if exc.details else None,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem_response(
            status=422,
            code="REQUEST_VALIDATION_ERROR",
            title="Request Validation Error",
            detail="One or more fields are invalid.",
            extra={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("api.unexpected_error", error=str(exc))
        return _problem_response(
            status=500,
            code="INTERNAL_ERROR",
            title="Internal Server Error",
            detail="An unexpected error occurred.",
        )