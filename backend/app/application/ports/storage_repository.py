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
    TrashCursorDTO,
)
from app.domain.storage.entities import (
    File,
    FileVersion,
    Folder,
    StorageEntry,
    StorageObject,
    TrashItem,
    UploadSession,
)


@dataclass(frozen=True, slots=True)
class StorageTreeNode:
    """Internal depth-ordered domain node used by recursive commands."""

    entry: Folder | File
    depth: int


@dataclass(frozen=True, slots=True)
class TrashedEntryRecord:
    """A trash tombstone joined to its deleted logical entry."""

    trash_item: TrashItem
    entry: Folder | File


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

    async def get_folder_path(
        self,
        *,
        owner_id: UUID,
        folder_id: UUID | None,
    ) -> tuple[Folder, ...]: ...

    async def logical_path_length(self, folder_id: UUID) -> int: ...

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

    async def get_storage_objects_by_keys(
        self,
        keys: tuple[str, ...],
    ) -> tuple[StorageObject, ...]: ...

    async def list_storage_objects(
        self,
        *,
        after_id: UUID | None,
        limit: int,
    ) -> tuple[tuple[StorageObject, ...], UUID | None]: ...

    async def claim_orphan_storage_objects(
        self,
        *,
        limit: int,
    ) -> tuple[tuple[StorageObject, ...], bool]:
        """Lock a bounded set of unreferenced ready objects for detachment."""
        ...

    async def delete_claimed_orphan_storage_object(self, object_id: UUID) -> bool:
        """Detach one still-unreferenced claimed object from database metadata."""
        ...

    async def save_entry(self, entry: StorageEntry) -> None: ...

    async def soft_delete_subtree(
        self, root_id: UUID, *, deleted_at: datetime
    ) -> int: ...

    async def restore_subtree(self, root_id: UUID, *, restored_at: datetime) -> int: ...

    async def get_current_version(self, file_id: UUID) -> FileVersion | None: ...

    async def get_current_versions_batch(
        self,
        file_ids: tuple[UUID, ...],
    ) -> dict[UUID, FileVersion]: ...

    def stream_subtree(self, root_id: UUID) -> AsyncIterator[StorageTreeNode]: ...

    async def add_trash_item(self, trash_item: TrashItem) -> None: ...

    async def get_trash_item(
        self,
        trash_item_id: UUID,
        *,
        for_update: bool = False,
    ) -> TrashItem | None: ...

    async def get_trash_item_by_entry(self, entry_id: UUID) -> TrashItem | None: ...

    async def list_trash(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: TrashCursorDTO | None,
    ) -> tuple[tuple[TrashedEntryRecord, ...], bool]: ...

    async def remove_trash_item(self, trash_item_id: UUID) -> None: ...

    async def hard_delete_subtree(self, root_id: UUID) -> int: ...

    async def add_upload_session(self, session: UploadSession) -> None: ...

    async def get_upload_session(
        self,
        upload_id: UUID,
        *,
        for_update: bool = False,
    ) -> UploadSession | None: ...

    async def save_upload_session(self, session: UploadSession) -> None: ...

    async def get_upload_sessions_by_ids(
        self,
        upload_ids: tuple[UUID, ...],
    ) -> tuple[UploadSession, ...]: ...

    async def claim_expired_upload_sessions(
        self,
        *,
        expired_at: datetime,
        limit: int,
    ) -> tuple[UploadSession, ...]: ...
