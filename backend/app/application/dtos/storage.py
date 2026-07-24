"""Storage command and read-model transfer objects."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.application.ports.file_storage import StorageKey
else:
    # Keep runtime annotation resolution independent from the ports package.
    StorageKey = str


class StorageEntryKind(StrEnum):
    FOLDER = "folder"
    FILE = "file"


class StorageSortField(StrEnum):
    NAME = "name"
    DATE = "date"
    SIZE = "size"
    TYPE = "type"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class StorageEntryDTO:
    id: UUID
    parent_id: UUID | None
    kind: StorageEntryKind
    name: str
    size: int | None
    mime_type: str | None
    extension: str | None
    checksum_sha256: str | None
    current_version_number: int | None
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False


@dataclass(frozen=True, slots=True)
class FileDetailsDTO:
    id: UUID
    parent_id: UUID
    name: str
    original_name: str
    size: int
    mime_type: str
    extension: str
    checksum_sha256: str
    current_version_number: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TrashItemDTO:
    id: UUID
    entry_id: UUID
    original_parent_id: UUID
    trashed_at: datetime


@dataclass(frozen=True, slots=True)
class TrashedEntryDTO:
    trash_item: TrashItemDTO
    entry: StorageEntryDTO


@dataclass(frozen=True, slots=True)
class TrashCursorDTO:
    trashed_at: datetime
    trash_item_id: UUID


@dataclass(frozen=True, slots=True)
class ListTrashQueryDTO:
    owner_id: UUID
    limit: int
    cursor: str | None


@dataclass(frozen=True, slots=True)
class PermanentDeleteResultDTO:
    deleted_entries: int


@dataclass(frozen=True, slots=True)
class StorageListFiltersDTO:
    name_contains: str | None = None
    kind: StorageEntryKind | None = None
    extension: str | None = None
    minimum_size: int | None = None
    maximum_size: int | None = None
    modified_from: datetime | None = None
    modified_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class StoragePageCursorDTO:
    sort_key: str
    entry_id: UUID


@dataclass(frozen=True, slots=True)
class ListFolderEntriesQueryDTO:
    owner_id: UUID
    folder_id: UUID
    limit: int
    cursor: str | None
    sort_by: StorageSortField
    direction: SortDirection
    filters: StorageListFiltersDTO


@dataclass(frozen=True, slots=True)
class UploadPolicyDTO:
    maximum_file_size: int
    maximum_chunk_size: int
    maximum_logical_path_length: int
    session_ttl_seconds: int
    allowed_extensions: frozenset[str]
    blocked_extensions: frozenset[str]
    allowed_mime_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class StartUploadCommandDTO:
    owner_id: UUID
    parent_id: UUID
    filename: str
    expected_size: int
    declared_mime_type: str


@dataclass(frozen=True, slots=True)
class AppendUploadChunkCommandDTO:
    owner_id: UUID
    upload_id: UUID
    offset: int
    chunks: AsyncIterator[bytes]


@dataclass(frozen=True, slots=True)
class CompleteUploadCommandDTO:
    owner_id: UUID
    upload_id: UUID


@dataclass(frozen=True, slots=True)
class CancelUploadCommandDTO:
    owner_id: UUID
    upload_id: UUID


@dataclass(frozen=True, slots=True)
class UploadSessionDTO:
    id: UUID
    parent_id: UUID
    filename: str
    expected_size: int
    uploaded_bytes: int
    declared_mime_type: str | None
    extension: str
    status: str
    expires_at: datetime
    checksum_sha256: str | None


@dataclass(frozen=True, slots=True)
class UploadChunkResultDTO:
    upload_id: UUID
    offset: int
    received_bytes: int
    chunk_sha256: str


@dataclass(frozen=True, slots=True)
class FileDownloadDTO:
    id: UUID
    storage_key: StorageKey
    filename: str
    size: int
    mime_type: str
    checksum_sha256: str
    version_number: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateFolderCommandDTO:
    owner_id: UUID
    parent_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class RenameEntryCommandDTO:
    owner_id: UUID
    entry_id: UUID
    new_name: str


@dataclass(frozen=True, slots=True)
class MoveEntryCommandDTO:
    owner_id: UUID
    entry_id: UUID
    destination_folder_id: UUID


@dataclass(frozen=True, slots=True)
class CopyEntryCommandDTO:
    owner_id: UUID
    entry_id: UUID
    destination_folder_id: UUID
    new_name: str | None = None


@dataclass(frozen=True, slots=True)
class TrashEntryCommandDTO:
    owner_id: UUID
    entry_id: UUID


@dataclass(frozen=True, slots=True)
class RestoreEntryCommandDTO:
    owner_id: UUID
    trash_item_id: UUID
    destination_folder_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PermanentlyDeleteCommandDTO:
    owner_id: UUID
    trash_item_id: UUID


@dataclass(frozen=True, slots=True)
class ReconcileStorageCommandDTO:
    """Bounded-policy request for a complete DB/filesystem reconciliation."""

    execute: bool = False
    grace_seconds: int = 86_400
    batch_size: int = 200
    verify_checksums: bool = False

    def __post_init__(self) -> None:
        if not 300 <= self.grace_seconds <= 30 * 86_400:
            raise ValueError("grace_seconds must be between 300 and 2592000")
        if not 1 <= self.batch_size <= 1_000:
            raise ValueError("batch_size must be between 1 and 1000")


@dataclass(frozen=True, slots=True)
class ReconcileStorageResultDTO:
    physical_objects_scanned: int = 0
    orphan_objects_found: int = 0
    orphan_objects_quarantined: int = 0
    staged_uploads_scanned: int = 0
    orphan_staging_found: int = 0
    orphan_staging_deleted: int = 0
    database_objects_scanned: int = 0
    missing_physical_objects: int = 0
    size_mismatches: int = 0
    checksum_mismatches: int = 0
