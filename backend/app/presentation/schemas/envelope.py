"""Uniform JSON response envelope."""

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    """Optional field-level error detail."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str | None = None
    message: str


class ApiError(BaseModel):
    """Stable public error information."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: tuple[ErrorDetail, ...] = ()


class ResponseMeta(BaseModel):
    """Metadata common to every JSON response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    next_cursor: str | None = None


class ApiResponse[DataT](BaseModel):
    """Uniform success or error response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: DataT | None
    error: ApiError | None
    meta: ResponseMeta


ErrorResponse = ApiResponse[None]


def success_response[DataT](
    data: DataT,
    *,
    request_id: str,
    next_cursor: str | None = None,
) -> ApiResponse[DataT]:
    """Create a typed successful envelope."""
    return ApiResponse(
        data=data,
        error=None,
        meta=ResponseMeta(request_id=request_id, next_cursor=next_cursor),
    )


def error_response(error: ApiError, *, request_id: str) -> ErrorResponse:
    """Create a typed failed envelope."""
    return ErrorResponse(
        data=None,
        error=error,
        meta=ResponseMeta(request_id=request_id),
    )
