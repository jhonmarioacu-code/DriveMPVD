"""RFC 9110 conditional and byte-range delivery helpers."""

import asyncio
import time
import unicodedata
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from urllib.parse import quote

from app.application.dtos.storage import FileDownloadDTO
from app.application.ports.download_services import (
    DownloadMetricDTO,
    DownloadMetricsRecorder,
)
from app.application.ports.file_storage import ByteRangeDTO, FileStorageProvider

_MAX_RANGES = 16


class RangeRequestError(ValueError):
    """The byte range is malformed or has no satisfiable member."""


@dataclass(frozen=True, slots=True)
class ResolvedByteRange:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def file_etag(file: FileDownloadDTO) -> str:
    return (
        f'"{file.checksum_sha256}-{file.version_number}-'
        f'{int(file.updated_at.timestamp() * 1_000_000)}"'
    )


def evaluate_preconditions(
    *,
    method: str,
    headers: dict[str, str],
    etag: str,
    last_modified: datetime,
) -> int | None:
    if_match = headers.get("if-match")
    if if_match is not None and not _strong_match(if_match, etag):
        return 412
    if_none_match = headers.get("if-none-match")
    if if_none_match is not None:
        if _weak_match(if_none_match, etag):
            return 304 if method in {"GET", "HEAD"} else 412
        return None
    if_modified_since = headers.get("if-modified-since")
    if if_modified_since is None:
        return None
    cached_at = _parse_http_date(if_modified_since)
    if cached_at is None:
        return None
    resource_time = last_modified.astimezone(UTC).replace(microsecond=0)
    return 304 if resource_time <= cached_at else None


def parse_ranges(value: str | None, *, size: int) -> tuple[ResolvedByteRange, ...]:
    if value is None or not value.casefold().startswith("bytes="):
        return ()
    members = value[6:].split(",")
    if not members or len(members) > _MAX_RANGES or size == 0:
        raise RangeRequestError
    resolved: list[ResolvedByteRange] = []
    try:
        for member in members:
            first, separator, last = member.strip().partition("-")
            if not separator or (not first and not last):
                raise RangeRequestError
            if not first:
                suffix_length = int(last)
                if suffix_length <= 0:
                    continue
                start = max(0, size - suffix_length)
                end = size - 1
            else:
                start = int(first)
                if start < 0 or start >= size:
                    continue
                end = size - 1 if not last else min(int(last), size - 1)
                if end < start:
                    continue
            resolved.append(ResolvedByteRange(start, end))
    except ValueError as exc:
        raise RangeRequestError from exc
    if not resolved:
        raise RangeRequestError
    return _coalesce_ranges(resolved)


def content_disposition(filename: str) -> str:
    normalized = unicodedata.normalize("NFKD", filename)
    fallback = normalized.encode("ascii", "ignore").decode()
    fallback = (
        "".join(
            (
                character
                if 32 <= ord(character) < 127 and character not in {'"', "\\"}
                else "_"
            )
            for character in fallback
        ).strip()
        or "download"
    )
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def base_download_headers(file: FileDownloadDTO, *, etag: str) -> dict[str, str]:
    return {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Last-Modified": format_datetime(
            file.updated_at.astimezone(UTC),
            usegmt=True,
        ),
        "Cache-Control": "private, max-age=0, must-revalidate",
        "Content-Disposition": content_disposition(file.filename),
    }


def multipart_boundary(etag: str) -> str:
    return f"drivempvd-{etag.strip(chr(34))[:32]}"


def multipart_length(
    ranges: Iterable[ResolvedByteRange],
    *,
    boundary: str,
    mime_type: str,
    total_size: int,
) -> int:
    length = 0
    for byte_range in ranges:
        length += len(_part_header(byte_range, boundary, mime_type, total_size))
        length += byte_range.length + 2
    return length + len(f"--{boundary}--\r\n".encode())


async def stream_download(
    *,
    storage: FileStorageProvider,
    file: FileDownloadDTO,
    ranges: tuple[ResolvedByteRange, ...],
    boundary: str | None,
    metrics: DownloadMetricsRecorder,
) -> AsyncIterator[bytes]:
    started_at = time.perf_counter()
    bytes_sent = 0
    completed = False
    outcome = "cancelled"
    try:
        if not ranges:
            async for chunk in storage.stream(file.storage_key):
                bytes_sent += len(chunk)
                yield chunk
        elif len(ranges) == 1:
            selected = ranges[0]
            async for chunk in storage.stream(
                file.storage_key,
                byte_range=ByteRangeDTO(selected.start, selected.end),
            ):
                bytes_sent += len(chunk)
                yield chunk
        else:
            assert boundary is not None
            for selected in ranges:
                yield _part_header(selected, boundary, file.mime_type, file.size)
                async for chunk in storage.stream(
                    file.storage_key,
                    byte_range=ByteRangeDTO(selected.start, selected.end),
                ):
                    bytes_sent += len(chunk)
                    yield chunk
                yield b"\r\n"
            yield f"--{boundary}--\r\n".encode()
        completed = True
        outcome = "success"
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except Exception:
        outcome = "error"
        raise
    finally:
        duration = max(0.0, time.perf_counter() - started_at)
        if not completed and outcome == "success":
            outcome = "cancelled"
        metrics.record(
            DownloadMetricDTO(
                outcome=outcome,
                duration_seconds=duration,
                bytes_sent=bytes_sent,
                average_bytes_per_second=(
                    bytes_sent / duration if duration > 0 else 0.0
                ),
            )
        )


def _part_header(
    byte_range: ResolvedByteRange,
    boundary: str,
    mime_type: str,
    total_size: int,
) -> bytes:
    return (
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n"
        f"Content-Range: bytes {byte_range.start}-{byte_range.end}/{total_size}\r\n"
        "\r\n"
    ).encode()


def _coalesce_ranges(
    ranges: list[ResolvedByteRange],
) -> tuple[ResolvedByteRange, ...]:
    merged: list[ResolvedByteRange] = []
    for current in sorted(ranges, key=lambda value: (value.start, value.end)):
        if merged and current.start <= merged[-1].end + 1:
            previous = merged[-1]
            merged[-1] = ResolvedByteRange(
                previous.start, max(previous.end, current.end)
            )
        else:
            merged.append(current)
    return tuple(merged)


def _strong_match(value: str, etag: str) -> bool:
    return any(candidate == "*" or candidate == etag for candidate in _tags(value))


def _weak_match(value: str, etag: str) -> bool:
    target = etag.removeprefix("W/")
    return any(
        candidate == "*" or candidate.removeprefix("W/") == target
        for candidate in _tags(value)
    )


def _tags(value: str) -> tuple[str, ...]:
    return tuple(candidate.strip() for candidate in value.split(","))


def _parse_http_date(value: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(value)
        return (
            parsed.replace(tzinfo=UTC)
            if parsed.tzinfo is None
            else parsed.astimezone(UTC)
        )
    except (TypeError, ValueError, OverflowError):
        return None
