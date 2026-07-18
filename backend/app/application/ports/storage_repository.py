"""Storage aggregate repository port."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dtos.storage import (
    SortDirection,
    StorageListFiltersDTO,
    StoragePageCursorDTO,
    StorageSortField,
)
from app.domain.storage.entities import (
    File,
    FileVersion,
    Folder,
    StorageEntry,
    StorageObject,
    TrashItem,
)


@dataclass(frozen=True, slots=True)
class StorageTreeNode:
    """Internal depth-ordered domain node used by recursive commands."""

    entry: Folder | File
    depth: int


class StorageRepository(Protocol):
    """Persist logical storage aggregates without exposing ORM models."""

    async def get_entry(
        self,
        entry_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> StorageEntry | None: ...

    async def get_folder(
        self,
        folder_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Folder | None: ...

    async def list_children(
        self,
        *,
        owner_id: UUID,
        parent_id: UUID,
        limit: int,
        filters: StorageListFiltersDTO,
        sort_by: StorageSortField,
        direction: SortDirection,
        cursor: StoragePageCursorDTO | None,
    ) -> tuple[tuple[Folder | File, ...], bool]: ...

    async def name_exists(
        self,
        *,
        parent_id: UUID,
        normalized_name: str,
        exclude_entry_id: UUID | None = None,
    ) -> bool: ...

    async def is_descendant(self, *, ancestor_id: UUID, candidate_id: UUID) -> bool: ...

    async def add_folder(self, folder: Folder) -> None: ...

    async def add_file(self, file: File, version: FileVersion) -> None: ...

    async def add_storage_object(self, storage_object: StorageObject) -> None: ...

    async def get_storage_object(self, object_id: UUID) -> StorageObject | None: ...

    async def save_entry(self, entry: StorageEntry) -> None: ...

    async def soft_delete_subtree(
        self, root_id: UUID, *, deleted_at: datetime
    ) -> int: ...

    async def restore_subtree(self, root_id: UUID, *, restored_at: datetime) -> int: ...

    async def get_current_version(self, file_id: UUID) -> FileVersion | None: ...

    def stream_subtree(self, root_id: UUID) -> AsyncIterator[StorageTreeNode]: ...

    async def add_trash_item(self, trash_item: TrashItem) -> None: ...

    async def get_trash_item(
        self,
        trash_item_id: UUID,
        *,
        for_update: bool = False,
    ) -> TrashItem | None: ...

    async def get_trash_item_by_entry(self, entry_id: UUID) -> TrashItem | None: ...

    async def remove_trash_item(self, trash_item_id: UUID) -> None: ...

    async def hard_delete_subtree(self, root_id: UUID) -> int: ...
