"""Streaming file storage port.

The contract deliberately exposes opaque keys and async byte streams. It can be
implemented by local storage, S3 or MinIO without changing application code.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import NewType, Protocol
from uuid import UUID

StorageKey = NewType("StorageKey", str)


@dataclass(frozen=True, slots=True)
class ByteRangeDTO:
    """Inclusive byte range requested from a stored object."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class StoredObjectDTO:
    """Metadata returned after atomically publishing an upload."""

    key: StorageKey
    size: int


class FileStorageProvider(Protocol):
    """Port for bounded-memory storage operations."""

    async def create_upload(self, upload_id: UUID) -> None:
        """Create an empty staging object."""
        ...

    async def append_chunk(
        self,
        upload_id: UUID,
        *,
        offset: int,
        chunks: AsyncIterator[bytes],
    ) -> int:
        """Append a streamed chunk and return the persisted offset."""
        ...

    async def publish_upload(
        self,
        upload_id: UUID,
        *,
        expected_size: int,
    ) -> StoredObjectDTO:
        """Atomically move a complete staging object into permanent storage."""
        ...

    def stream(
        self,
        key: StorageKey,
        *,
        byte_range: ByteRangeDTO | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream an object or range without materializing it in memory."""
        ...

    async def delete(self, key: StorageKey) -> None:
        """Delete an object idempotently."""
        ...
