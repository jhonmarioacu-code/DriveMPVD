"""Translate all known exception layers into the uniform API envelope."""

import logging
from typing import Protocol, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.application.exceptions import (
    ApplicationError,
    ApplicationValidationError,
    ConflictError,
    ResourceNotFoundError,
)
from app.domain.exceptions import DomainError
from app.presentation.schemas.envelope import ApiError, ErrorDetail, error_response

logger = logging.getLogger(__name__)


class PublicLayerError(Protocol):
    """Safe error contract supplied by an outer layer at composition time."""

    code: str
    public_message: str


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _json_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: tuple[ErrorDetail, ...] = (),
) -> JSONResponse:
    envelope = error_response(
        ApiError(code=code, message=message, details=details),
        request_id=_request_id(request),
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
    )


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    """Return a stable client error for a domain invariant violation."""
    assert isinstance(exc, DomainError)
    return _json_error(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code=exc.code,
        message=exc.public_message,
    )


async def handle_application_error(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Map expected use-case errors without exposing adapter details."""
    assert isinstance(exc, ApplicationError)
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    if isinstance(exc, ResourceNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, ApplicationValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return _json_error(
        request,
        status_code=status_code,
        code=exc.code,
        message=exc.public_message,
    )


async def handle_infrastructure_error(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Log infrastructure failures and return a sanitized service error."""
    public_error = cast(PublicLayerError, exc)
    logger.error(
        "infrastructure_error",
        extra={"request_id": _request_id(request), "error_code": public_error.code},
        exc_info=exc,
    )
    return _json_error(
        request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code=public_error.code,
        message=public_error.public_message,
    )


async def handle_request_validation_error(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Normalize FastAPI/Pydantic validation errors."""
    assert isinstance(exc, RequestValidationError)
    details = tuple(
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            message=str(error["msg"]),
        )
        for error in exc.errors()
    )
    return _json_error(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="request.validation_error",
        message="The request contains invalid values.",
        details=details,
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Normalize framework HTTP errors such as missing routes."""
    assert isinstance(exc, HTTPException)
    message = exc.detail if isinstance(exc.detail, str) else "The request failed."
    return _json_error(
        request,
        status_code=exc.status_code,
        code=f"http.{exc.status_code}",
        message=message,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Contain unexpected errors and correlate the private stack trace."""
    logger.exception(
        "unexpected_error",
        extra={
            "request_id": _request_id(request),
            "error_code": "internal.error",
        },
        exc_info=exc,
    )
    return _json_error(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal.error",
        message="An unexpected error occurred.",
    )


def register_exception_handlers(
    app: FastAPI,
    *,
    infrastructure_error_type: type[Exception],
) -> None:
    """Register the single global exception translation table."""
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(ApplicationError, handle_application_error)
    app.add_exception_handler(infrastructure_error_type, handle_infrastructure_error)
    app.add_exception_handler(
        RequestValidationError,
        handle_request_validation_error,
    )
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
