"""Streaming file storage port.

The contract deliberately exposes opaque keys and async byte streams. It can be
implemented by local storage, S3 or MinIO without changing application code.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True, slots=True)
class PhysicalObjectDTO:
    """One opaque object discovered during a filesystem reconciliation."""

    key: StorageKey
    size: int
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class StagedUploadDTO:
    """One staged upload discovered independently from PostgreSQL."""

    upload_id: UUID
    size: int
    modified_at: datetime


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

    def stream_upload(self, upload_id: UUID) -> AsyncIterator[bytes]:
        """Stream staged bytes for integrity and inspection passes."""
        ...

    async def upload_size(self, upload_id: UUID) -> int:
        """Return the actual persisted staging length."""
        ...

    async def discard_upload(self, upload_id: UUID) -> None:
        """Remove staging content idempotently."""
        ...

    async def truncate_upload(self, upload_id: UUID, *, offset: int) -> None:
        """Compensate an append whose metadata transaction did not commit."""
        ...

    def stream(
        self,
        key: StorageKey,
        *,
        byte_range: ByteRangeDTO | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream an object or range without materializing it in memory."""
        ...

    async def stat(self, key: StorageKey) -> StoredObjectDTO | None:
        """Return physical metadata, or None when the object is absent."""
        ...

    async def delete(self, key: StorageKey) -> None:
        """Delete an object idempotently."""
        ...

    def list_objects(self) -> AsyncIterator[PhysicalObjectDTO]:
        """Walk physical objects with bounded per-directory memory."""
        ...

    def list_staged_uploads(self) -> AsyncIterator[StagedUploadDTO]:
        """Walk valid opaque staging files for reconciliation."""
        ...

    async def quarantine(self, key: StorageKey) -> None:
        """Move an unreferenced object to recoverable ``lost+found`` storage."""
        ...
