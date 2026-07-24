"""Storage domain entities without ORM or physical filesystem dependencies."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.storage.enums import (
    DerivedAssetStatus,
    EntryType,
    StorageObjectStatus,
    UploadStatus,
)
from app.domain.storage.exceptions import InvalidStateTransitionError
from app.domain.storage.value_objects import EntryName, Sha256Checksum


@dataclass(slots=True)
class StorageEntry:
    id: UUID
    owner_id: UUID
    parent_id: UUID | None
    name: str
    normalized_name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def rename(self, name: EntryName, *, now: datetime) -> None:
        if self.deleted_at is not None:
            raise InvalidStateTransitionError("A trashed entry cannot be renamed.")
        self.name = name.value
        self.normalized_name = name.normalized
        self.updated_at = now

    def move(self, parent_id: UUID, *, now: datetime) -> None:
        if self.deleted_at is not None:
            raise InvalidStateTransitionError("A trashed entry cannot be moved.")
        self.parent_id = parent_id
        self.updated_at = now

    def move_to_trash(self, *, now: datetime) -> None:
        if self.parent_id is None:
            raise InvalidStateTransitionError("The storage root cannot be trashed.")
        if self.deleted_at is None:
            self.deleted_at = now
            self.updated_at = now

    def restore(self, *, parent_id: UUID, now: datetime) -> None:
        if self.deleted_at is None:
            raise InvalidStateTransitionError("The entry is not in the trash.")
        self.parent_id = parent_id
        self.deleted_at = None
        self.updated_at = now


@dataclass(slots=True)
class Folder(StorageEntry):
    """Logical folder using adjacency via `parent_id`; root has no parent."""

    entry_type: EntryType = EntryType.FOLDER


@dataclass(slots=True)
class File(StorageEntry):
    """Logical file whose immutable bytes live in a StorageObject."""

    original_name: str = ""
    internal_name: str = ""
    size: int = 0
    mime_type: str = "application/octet-stream"
    extension: str = ""
    checksum_sha256: str = ""
    current_version_number: int = 1
    entry_type: EntryType = EntryType.FILE

    def __post_init__(self) -> None:
        Sha256Checksum.create(self.checksum_sha256)
        if self.size < 0 or self.current_version_number < 1:
            raise InvalidStateTransitionError("File metadata is inconsistent.")


@dataclass(slots=True)
class StorageObject:
    """Provider-independent immutable content object, ready for future dedup."""

    id: UUID
    storage_key: str
    size: int
    mime_type: str
    checksum_sha256: str
    status: StorageObjectStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        Sha256Checksum.create(self.checksum_sha256)
        if self.size < 0 or not self.storage_key:
            raise InvalidStateTransitionError("Storage object metadata is invalid.")


@dataclass(frozen=True, slots=True)
class FileVersion:
    """Immutable file metadata snapshot pointing at an immutable object."""

    id: UUID
    file_id: UUID
    storage_object_id: UUID
    version_number: int
    original_name: str
    size: int
    mime_type: str
    extension: str
    checksum_sha256: str
    created_by: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        Sha256Checksum.create(self.checksum_sha256)
        if self.version_number < 1 or self.size < 0:
            raise InvalidStateTransitionError("File version metadata is invalid.")


@dataclass(slots=True)
class Thumbnail:
    id: UUID
    file_version_id: UUID
    storage_object_id: UUID | None
    variant: str
    width: int | None
    height: int | None
    status: DerivedAssetStatus
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Preview:
    id: UUID
    file_version_id: UUID
    storage_object_id: UUID | None
    variant: str
    mime_type: str | None
    status: DerivedAssetStatus
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class UploadSession:
    """Future resumable upload state; bytes remain behind FileStorageProvider."""

    id: UUID
    owner_id: UUID
    parent_id: UUID
    original_name: str
    internal_name: str
    expected_size: int
    uploaded_bytes: int
    mime_type: str | None
    extension: str
    checksum_sha256: str | None
    staging_key: str
    status: UploadStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    def record_progress(self, *, persisted_offset: int, now: datetime) -> None:
        if self.status not in {UploadStatus.CREATED, UploadStatus.UPLOADING}:
            raise InvalidStateTransitionError()
        if not self.uploaded_bytes <= persisted_offset <= self.expected_size:
            raise InvalidStateTransitionError("Upload offset is invalid.")
        self.uploaded_bytes = persisted_offset
        self.status = UploadStatus.UPLOADING
        self.updated_at = now

    def complete(self, *, checksum: Sha256Checksum, now: datetime) -> None:
        if self.uploaded_bytes != self.expected_size:
            raise InvalidStateTransitionError("Upload is incomplete.")
        self.checksum_sha256 = checksum.value
        self.status = UploadStatus.COMPLETED
        self.updated_at = now

    def cancel(self, *, now: datetime) -> None:
        if self.status is UploadStatus.COMPLETED:
            raise InvalidStateTransitionError("A completed upload cannot be cancelled.")
        if self.status is UploadStatus.CANCELLED:
            return
        self.status = UploadStatus.CANCELLED
        self.updated_at = now

    def expire(self, *, now: datetime) -> None:
        if self.status not in {UploadStatus.CREATED, UploadStatus.UPLOADING}:
            raise InvalidStateTransitionError("Only an active upload can expire.")
        if self.expires_at > now:
            raise InvalidStateTransitionError("The upload session has not expired.")
        self.status = UploadStatus.EXPIRED
        self.updated_at = now


@dataclass(frozen=True, slots=True)
class TrashItem:
    """Tombstone for a deleted subtree root, preserving its restore location."""

    id: UUID
    entry_id: UUID
    original_parent_id: UUID
    deleted_by: UUID
    trashed_at: datetime
