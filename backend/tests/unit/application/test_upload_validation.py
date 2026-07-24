from collections.abc import AsyncIterator

import pytest

from app.application.dtos.storage import UploadPolicyDTO
from app.application.exceptions import UploadValidationError
from app.application.use_cases.storage.uploads import (
    _BoundedHashingStream,
    _canonical_mime,
    _inspect_stream,
    _validate_mime,
    _validate_start_policy,
)


def _policy(
    *,
    allowed_extensions: frozenset[str] = frozenset({"pdf"}),
    blocked_extensions: frozenset[str] = frozenset({"exe"}),
    allowed_mime_types: frozenset[str] = frozenset({"application/pdf"}),
) -> UploadPolicyDTO:
    return UploadPolicyDTO(
        maximum_file_size=100,
        maximum_chunk_size=8,
        maximum_logical_path_length=255,
        session_ttl_seconds=60,
        allowed_extensions=allowed_extensions,
        blocked_extensions=blocked_extensions,
        allowed_mime_types=allowed_mime_types,
    )


@pytest.mark.parametrize("value", ["invalid", "x" * 256])
def test_declared_mime_must_be_structurally_valid(value: str) -> None:
    with pytest.raises(UploadValidationError):
        _canonical_mime(value)
    assert _canonical_mime(" Application/PDF; charset=binary ") == "application/pdf"


@pytest.mark.parametrize(
    ("size", "extension", "mime_type"),
    [
        (-1, "pdf", "application/pdf"),
        (101, "pdf", "application/pdf"),
        (1, "exe", "application/pdf"),
        (1, "txt", "application/pdf"),
        (1, "pdf", "text/plain"),
    ],
)
def test_start_policy_rejects_size_extension_and_mime_violations(
    size: int,
    extension: str,
    mime_type: str,
) -> None:
    with pytest.raises(UploadValidationError):
        _validate_start_policy(size, extension, mime_type, _policy())


def test_mime_validation_allows_generic_and_known_zip_containers() -> None:
    unrestricted = _policy(
        allowed_extensions=frozenset(), allowed_mime_types=frozenset()
    )
    _validate_mime("application/octet-stream", "application/pdf", unrestricted)
    _validate_mime(None, "application/pdf", unrestricted)
    _validate_mime(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        unrestricted,
    )
    with pytest.raises(UploadValidationError):
        _validate_mime("text/plain", "application/pdf", unrestricted)
    with pytest.raises(UploadValidationError):
        _validate_mime("application/pdf", "text/plain", _policy())


async def _chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


async def test_bounded_hashing_stream_enforces_chunk_and_remaining_sizes() -> None:
    oversized = _BoundedHashingStream(_chunks(b"12345", b"6789"), maximum_size=8)
    assert await anext(oversized) == b"12345"
    with pytest.raises(UploadValidationError):
        await anext(oversized)

    remaining = _BoundedHashingStream(_chunks(b"1234"), maximum_size=8)
    remaining.set_remaining(3)
    with pytest.raises(UploadValidationError):
        await anext(remaining)


async def test_stream_inspection_hashes_all_bytes_and_caps_prefix() -> None:
    payload = b"a" * (70 * 1024)
    checksum, size, prefix = await _inspect_stream(
        _chunks(payload[:100], payload[100:])
    )
    assert len(checksum) == 64
    assert size == len(payload)
    assert prefix == payload[: 64 * 1024]
