"""Storage command and read-model transfer objects."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


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
