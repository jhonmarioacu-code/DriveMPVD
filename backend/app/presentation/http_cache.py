"""Conditional HTTP caching helpers for metadata resources."""

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime

from fastapi import Request, Response, status

_CACHE_CONTROL = "private, max-age=0, must-revalidate"


def metadata_etag(parts: Iterable[str]) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f'"{digest}"'


def apply_cache_headers(
    response: Response,
    *,
    etag: str,
    last_modified: datetime | None,
) -> None:
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _CACHE_CONTROL
    if last_modified is not None:
        response.headers["Last-Modified"] = _http_date(last_modified)


def conditional_not_modified(
    request: Request,
    *,
    etag: str,
    last_modified: datetime | None,
) -> Response | None:
    if_none_match = request.headers.get("if-none-match")
    if if_none_match is not None:
        candidates = {
            item.strip().removeprefix("W/") for item in if_none_match.split(",")
        }
        if "*" in candidates or etag in candidates:
            return _not_modified_response(etag, last_modified)
        return None
    if_modified_since = request.headers.get("if-modified-since")
    if if_modified_since is None or last_modified is None:
        return None
    try:
        cached_at = parsedate_to_datetime(if_modified_since)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=UTC)
    except (TypeError, ValueError, OverflowError):
        return None
    resource_time = last_modified.astimezone(UTC).replace(microsecond=0)
    if resource_time <= cached_at.astimezone(UTC):
        return _not_modified_response(etag, last_modified)
    return None


def _not_modified_response(etag: str, last_modified: datetime | None) -> Response:
    response = Response(status_code=status.HTTP_304_NOT_MODIFIED)
    apply_cache_headers(response, etag=etag, last_modified=last_modified)
    return response


def _http_date(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return format_datetime(aware.astimezone(UTC), usegmt=True)
