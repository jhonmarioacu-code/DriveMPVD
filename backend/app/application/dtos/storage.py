"""Storage use-case commands and query transfer objects."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.storage.entities import File, Folder


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
class StorageTreeNodeDTO:
    """One depth-ordered domain entry streamed from a subtree query."""

    entry: Folder | File
    depth: int
