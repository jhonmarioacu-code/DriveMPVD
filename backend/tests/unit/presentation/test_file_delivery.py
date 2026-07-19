from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest

from app.application.dtos.storage import FileDownloadDTO
from app.application.ports.download_services import DownloadMetricDTO
from app.application.ports.file_storage import (
    ByteRangeDTO,
    FileStorageProvider,
    StorageKey,
)
from app.presentation.file_delivery import (
    RangeRequestError,
    base_download_headers,
    content_disposition,
    evaluate_preconditions,
    file_etag,
    multipart_boundary,
    multipart_length,
    parse_ranges,
    stream_download,
)

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


class MemoryReader:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def stream(
        self,
        key: StorageKey,
        *,
        byte_range: ByteRangeDTO | None = None,
    ) -> AsyncIterator[bytes]:
        del key

        async def chunks() -> AsyncIterator[bytes]:
            selected = self.content
            if byte_range is not None:
                selected = selected[byte_range.start : byte_range.end + 1]
            midpoint = max(1, len(selected) // 2)
            yield selected[:midpoint]
            if selected[midpoint:]:
                yield selected[midpoint:]

        return chunks()


class MetricsRecorder:
    def __init__(self) -> None:
        self.items: list[DownloadMetricDTO] = []

    def record(self, metric: DownloadMetricDTO) -> None:
        self.items.append(metric)


def _file(size: int = 26) -> FileDownloadDTO:
    return FileDownloadDTO(
        id=uuid4(),
        storage_key=StorageKey("objects/file"),
        filename="résumé 2026.pdf",
        size=size,
        mime_type="application/pdf",
        checksum_sha256="a" * 64,
        version_number=1,
        updated_at=NOW,
    )


def test_preconditions_follow_rfc_precedence() -> None:
    file = _file()
    etag = file_etag(file)

    assert (
        evaluate_preconditions(
            method="GET",
            headers={"if-match": '"different"'},
            etag=etag,
            last_modified=NOW,
        )
        == 412
    )
    assert (
        evaluate_preconditions(
            method="GET",
            headers={"if-match": f"W/{etag}"},
            etag=etag,
            last_modified=NOW,
        )
        == 412
    )
    assert (
        evaluate_preconditions(
            method="GET", headers={"if-match": "*"}, etag=etag, last_modified=NOW
        )
        is None
    )
    assert (
        evaluate_preconditions(
            method="GET",
            headers={"if-none-match": f"W/{etag}"},
            etag=etag,
            last_modified=NOW,
        )
        == 304
    )
    assert (
        evaluate_preconditions(
            method="GET",
            headers={
                "if-none-match": '"different"',
                "if-modified-since": "Sat, 18 Jul 2037 12:00:00 GMT",
            },
            etag=etag,
            last_modified=NOW,
        )
        is None
    )
    assert (
        evaluate_preconditions(
            method="HEAD",
            headers={"if-modified-since": "Sat, 18 Jul 2037 12:00:00 GMT"},
            etag=etag,
            last_modified=NOW,
        )
        == 304
    )


def test_ranges_resolve_suffix_open_and_multiple_members() -> None:
    assert parse_ranges(None, size=100) == ()
    assert parse_ranges("items=0-2", size=100) == ()
    assert [(item.start, item.end) for item in parse_ranges("bytes=10-", size=100)] == [
        (10, 99)
    ]
    assert [(item.start, item.end) for item in parse_ranges("bytes=-10", size=100)] == [
        (90, 99)
    ]
    assert [
        (item.start, item.end) for item in parse_ranges("bytes=0-4,3-8,20-29", size=100)
    ] == [(0, 8), (20, 29)]

    for value, size in (("bytes=", 100), ("bytes=500-600", 100), ("bytes=0-1", 0)):
        with pytest.raises(RangeRequestError):
            parse_ranges(value, size=size)


def test_headers_encode_utf8_filename_and_private_cache() -> None:
    file = _file()
    disposition = content_disposition(file.filename)
    headers = base_download_headers(file, etag=file_etag(file))

    assert "filename*=UTF-8''r%C3%A9sum%C3%A9%202026.pdf" in disposition
    assert 'filename="resume 2026.pdf"' in disposition
    assert headers["Accept-Ranges"] == "bytes"
    assert headers["Cache-Control"].startswith("private")
    assert headers["Last-Modified"].endswith("GMT")


async def test_multipart_stream_length_and_metrics_are_exact() -> None:
    content = b"abcdefghijklmnopqrstuvwxyz"
    file = _file(len(content))
    ranges = parse_ranges("bytes=0-2,20-25", size=len(content))
    boundary = multipart_boundary(file_etag(file))
    recorder = MetricsRecorder()

    body = b"".join(
        [
            chunk
            async for chunk in stream_download(
                storage=cast(FileStorageProvider, MemoryReader(content)),
                file=file,
                ranges=ranges,
                boundary=boundary,
                metrics=recorder,
            )
        ]
    )

    assert len(body) == multipart_length(
        ranges,
        boundary=boundary,
        mime_type=file.mime_type,
        total_size=file.size,
    )
    assert b"Content-Range: bytes 0-2/26" in body
    assert b"abc" in body
    assert b"uvwxyz" in body
    assert recorder.items[0].outcome == "success"
    assert recorder.items[0].bytes_sent == 9


async def test_early_stream_close_records_client_cancellation() -> None:
    content = b"abcdefghijklmnopqrstuvwxyz"
    recorder = MetricsRecorder()
    stream = stream_download(
        storage=cast(FileStorageProvider, MemoryReader(content)),
        file=_file(len(content)),
        ranges=(),
        boundary=None,
        metrics=recorder,
    )

    assert await anext(stream)
    await cast(AsyncGenerator[bytes], stream).aclose()

    assert recorder.items[0].outcome == "cancelled"
    assert 0 < recorder.items[0].bytes_sent < len(content)


def test_modified_since_older_or_invalid_does_not_suppress_body() -> None:
    file = _file()
    etag = file_etag(file)
    older = NOW - timedelta(days=1)
    assert (
        evaluate_preconditions(
            method="GET",
            headers={"if-modified-since": older.strftime("%a, %d %b %Y %H:%M:%S GMT")},
            etag=etag,
            last_modified=NOW,
        )
        is None
    )
    assert (
        evaluate_preconditions(
            method="GET",
            headers={"if-modified-since": "invalid"},
            etag=etag,
            last_modified=NOW,
        )
        is None
    )
