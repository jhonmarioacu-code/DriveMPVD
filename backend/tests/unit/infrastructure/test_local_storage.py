from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.ports.file_storage import ByteRangeDTO, StorageKey
from app.infrastructure.exceptions import FileStorageError
from app.infrastructure.storage.local import LocalFileStorageProvider
from app.infrastructure.storage.mime import SignatureMimeDetector


async def _chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


async def _failing_chunks() -> AsyncIterator[bytes]:
    yield b"partial"
    raise OSError("simulated source failure")


async def test_local_provider_stages_publishes_ranges_and_deletes(
    tmp_path: Path,
) -> None:
    provider = LocalFileStorageProvider(tmp_path, stream_block_size=3)
    upload_id = uuid4()
    await provider.create_upload(upload_id)

    assert (
        await provider.append_chunk(
            upload_id,
            offset=0,
            chunks=_chunks(b"abc", b"def"),
        )
        == 6
    )
    assert (
        b"".join([chunk async for chunk in provider.stream_upload(upload_id)])
        == b"abcdef"
    )
    stored = await provider.publish_upload(upload_id, expected_size=6)
    assert stored.size == 6
    assert b"".join([chunk async for chunk in provider.stream(stored.key)]) == b"abcdef"
    assert (
        b"".join(
            [
                chunk
                async for chunk in provider.stream(
                    stored.key,
                    byte_range=ByteRangeDTO(start=1, end=4),
                )
            ]
        )
        == b"bcde"
    )

    await provider.delete(stored.key)
    await provider.delete(stored.key)


async def test_local_provider_rolls_back_failed_append_and_confines_keys(
    tmp_path: Path,
) -> None:
    provider = LocalFileStorageProvider(tmp_path)
    upload_id = uuid4()
    await provider.create_upload(upload_id)

    with pytest.raises(FileStorageError):
        await provider.append_chunk(upload_id, offset=0, chunks=_failing_chunks())
    assert await provider.upload_size(upload_id) == 0
    with pytest.raises(FileStorageError):
        await provider.append_chunk(upload_id, offset=1, chunks=_chunks(b"x"))
    with pytest.raises(FileStorageError):
        _ = [chunk async for chunk in provider.stream(StorageKey("../outside"))]

    await provider.truncate_upload(upload_id, offset=0)
    await provider.discard_upload(upload_id)


async def test_local_provider_coalesces_small_writes_and_handles_partial_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LocalFileStorageProvider(
        tmp_path,
        stream_block_size=4,
        write_buffer_size=4,
    )
    upload_id = uuid4()
    await provider.create_upload(upload_id)

    writes = 0
    original_write_all = LocalFileStorageProvider._write_all

    def count_write(handle: object, payload: bytes) -> None:
        nonlocal writes
        writes += 1
        original_write_all(handle, payload)

    monkeypatch.setattr(
        LocalFileStorageProvider,
        "_write_all",
        staticmethod(count_write),
    )

    assert (
        await provider.append_chunk(
            upload_id,
            offset=0,
            chunks=_chunks(b"a", b"b", b"c", b"d", b"e", b"f", b"g", b"h", b"i"),
        )
        == 9
    )
    assert writes == 3

    class PartialWriter:
        def __init__(self) -> None:
            self.buffer = BytesIO()

        def write(self, value: bytes) -> int:
            portion = value[:2]
            self.buffer.write(portion)
            return len(portion)

    partial_writer = PartialWriter()
    LocalFileStorageProvider._write_all(partial_writer, b"abcdef")
    assert partial_writer.buffer.getvalue() == b"abcdef"
    await provider.discard_upload(upload_id)


@pytest.mark.parametrize(
    ("content", "filename", "expected"),
    [
        (b"%PDF-1.7", "a.pdf", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n", "a.png", "image/png"),
        (b"PK\x03\x04data", "a.zip", "application/zip"),
        (b"plain utf-8 text", "a.txt", "text/plain"),
        (b"\x00\x01binary", "a.bin", "application/octet-stream"),
        (b"", "empty.bin", "application/x-empty"),
    ],
)
def test_signature_mime_detector(
    content: bytes,
    filename: str,
    expected: str,
) -> None:
    assert SignatureMimeDetector().detect(content, filename=filename) == expected
