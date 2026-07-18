"""SQLAlchemy repository for logical storage aggregates."""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, literal, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.storage import StorageTreeNodeDTO
from app.domain.storage.entities import (
    File,
    FileVersion,
    Folder,
    StorageEntry,
    StorageObject,
    TrashItem,
)
from app.domain.storage.enums import EntryType, StorageObjectStatus
from app.infrastructure.exceptions import PersistenceError
from app.infrastructure.persistence.models.storage import (
    FileMetadataModel,
    FileVersionModel,
    StorageEntryModel,
    StorageObjectModel,
    TrashItemModel,
)


class SQLAlchemyStorageRepository:
    """Map domain entries explicitly and keep recursive queries bounded in memory."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_entry(
        self,
        entry_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> StorageEntry | None:
        statement = (
            select(StorageEntryModel, FileMetadataModel)
            .outerjoin(
                FileMetadataModel, FileMetadataModel.entry_id == StorageEntryModel.id
            )
            .where(StorageEntryModel.id == entry_id)
        )
        if not include_deleted:
            statement = statement.where(StorageEntryModel.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update(of=StorageEntryModel)
        try:
            row = (await self._session.execute(statement)).one_or_none()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if row is None else self._to_entry(row[0], row[1])

    async def get_folder(
        self,
        folder_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Folder | None:
        entry = await self.get_entry(
            folder_id,
            include_deleted=include_deleted,
            for_update=for_update,
        )
        return entry if isinstance(entry, Folder) else None

    async def name_exists(
        self,
        *,
        parent_id: UUID,
        normalized_name: str,
        exclude_entry_id: UUID | None = None,
    ) -> bool:
        statement = select(StorageEntryModel.id).where(
            StorageEntryModel.parent_id == parent_id,
            StorageEntryModel.normalized_name == normalized_name,
            StorageEntryModel.deleted_at.is_(None),
        )
        if exclude_entry_id is not None:
            statement = statement.where(StorageEntryModel.id != exclude_entry_id)
        try:
            return await self._session.scalar(statement) is not None
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    async def is_descendant(self, *, ancestor_id: UUID, candidate_id: UUID) -> bool:
        tree = (
            select(StorageEntryModel.id)
            .where(StorageEntryModel.id == ancestor_id)
            .cte("descendants", recursive=True)
        )
        tree = tree.union_all(
            select(StorageEntryModel.id).join(
                tree,
                StorageEntryModel.parent_id == tree.c.id,
            )
        )
        try:
            return (
                await self._session.scalar(
                    select(tree.c.id).where(
                        tree.c.id == candidate_id,
                        tree.c.id != ancestor_id,
                    )
                )
                is not None
            )
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    async def add_folder(self, folder: Folder) -> None:
        self._session.add(self._entry_model(folder))
        await self._flush()

    async def add_file(self, file: File, version: FileVersion) -> None:
        self._session.add(self._entry_model(file))
        await self._flush()
        self._session.add(
            FileMetadataModel(
                entry_id=file.id,
                original_name=file.original_name,
                internal_name=file.internal_name,
                size=file.size,
                mime_type=file.mime_type,
                extension=file.extension,
                checksum_sha256=file.checksum_sha256,
                current_version_number=file.current_version_number,
            )
        )
        await self._flush()
        self._session.add(self._version_model(version))
        await self._flush()

    async def add_storage_object(self, storage_object: StorageObject) -> None:
        self._session.add(
            StorageObjectModel(
                id=storage_object.id,
                storage_key=storage_object.storage_key,
                size=storage_object.size,
                mime_type=storage_object.mime_type,
                checksum_sha256=storage_object.checksum_sha256,
                status=storage_object.status.value,
                created_at=storage_object.created_at,
                updated_at=storage_object.updated_at,
                deleted_at=storage_object.deleted_at,
            )
        )
        await self._flush()

    async def get_storage_object(self, object_id: UUID) -> StorageObject | None:
        try:
            model = await self._session.get(StorageObjectModel, object_id)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        if model is None:
            return None
        return StorageObject(
            id=model.id,
            storage_key=model.storage_key,
            size=model.size,
            mime_type=model.mime_type,
            checksum_sha256=model.checksum_sha256,
            status=StorageObjectStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )

    async def save_entry(self, entry: StorageEntry) -> None:
        statement = (
            update(StorageEntryModel)
            .where(StorageEntryModel.id == entry.id)
            .values(
                parent_id=entry.parent_id,
                name=entry.name,
                normalized_name=entry.normalized_name,
                updated_at=entry.updated_at,
                deleted_at=entry.deleted_at,
            )
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        if result.rowcount != 1:
            raise PersistenceError("The storage entry no longer exists.")

    async def soft_delete_subtree(
        self,
        root_id: UUID,
        *,
        deleted_at: datetime,
    ) -> int:
        return await self._update_subtree_deletion(root_id, deleted_at=deleted_at)

    async def restore_subtree(
        self,
        root_id: UUID,
        *,
        restored_at: datetime,
    ) -> int:
        return await self._update_subtree_deletion(
            root_id,
            deleted_at=None,
            updated_at=restored_at,
        )

    async def get_current_version(self, file_id: UUID) -> FileVersion | None:
        statement = (
            select(FileVersionModel)
            .join(
                FileMetadataModel,
                FileMetadataModel.entry_id == FileVersionModel.file_id,
            )
            .where(
                FileVersionModel.file_id == file_id,
                FileVersionModel.version_number
                == FileMetadataModel.current_version_number,
            )
        )
        try:
            model = await self._session.scalar(statement)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if model is None else self._to_version(model)

    async def stream_subtree(self, root_id: UUID) -> AsyncIterator[StorageTreeNodeDTO]:
        tree = (
            select(
                StorageEntryModel.id.label("id"),
                literal(0).label("depth"),
            )
            .where(StorageEntryModel.id == root_id)
            .cte("storage_subtree", recursive=True)
        )
        tree = tree.union_all(
            select(
                StorageEntryModel.id,
                (tree.c.depth + 1).label("depth"),
            ).join(tree, StorageEntryModel.parent_id == tree.c.id)
        )
        statement = (
            select(StorageEntryModel, FileMetadataModel, tree.c.depth)
            .join(tree, tree.c.id == StorageEntryModel.id)
            .outerjoin(
                FileMetadataModel, FileMetadataModel.entry_id == StorageEntryModel.id
            )
            .where(StorageEntryModel.deleted_at.is_(None))
            .order_by(tree.c.depth, StorageEntryModel.created_at, StorageEntryModel.id)
        )
        try:
            result = await self._session.stream(statement)
            async for entry_model, file_model, depth in result:
                yield StorageTreeNodeDTO(
                    entry=self._to_entry(entry_model, file_model),
                    depth=int(depth),
                )
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    async def add_trash_item(self, trash_item: TrashItem) -> None:
        self._session.add(
            TrashItemModel(
                id=trash_item.id,
                entry_id=trash_item.entry_id,
                original_parent_id=trash_item.original_parent_id,
                deleted_by=trash_item.deleted_by,
                trashed_at=trash_item.trashed_at,
            )
        )
        await self._flush()

    async def get_trash_item(
        self,
        trash_item_id: UUID,
        *,
        for_update: bool = False,
    ) -> TrashItem | None:
        statement = select(TrashItemModel).where(TrashItemModel.id == trash_item_id)
        if for_update:
            statement = statement.with_for_update()
        try:
            model = await self._session.scalar(statement)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if model is None else self._to_trash(model)

    async def get_trash_item_by_entry(self, entry_id: UUID) -> TrashItem | None:
        try:
            model = await self._session.scalar(
                select(TrashItemModel).where(TrashItemModel.entry_id == entry_id)
            )
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if model is None else self._to_trash(model)

    async def remove_trash_item(self, trash_item_id: UUID) -> None:
        try:
            await self._session.execute(
                delete(TrashItemModel).where(TrashItemModel.id == trash_item_id)
            )
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    async def hard_delete_subtree(self, root_id: UUID) -> int:
        tree = (
            select(StorageEntryModel.id)
            .where(StorageEntryModel.id == root_id)
            .cte("purged_subtree", recursive=True)
        )
        tree = tree.union_all(
            select(StorageEntryModel.id).join(
                tree,
                StorageEntryModel.parent_id == tree.c.id,
            )
        )
        statement = delete(StorageEntryModel).where(
            StorageEntryModel.id.in_(select(tree.c.id))
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return result.rowcount

    async def _update_subtree_deletion(
        self,
        root_id: UUID,
        *,
        deleted_at: datetime | None,
        updated_at: datetime | None = None,
    ) -> int:
        tree = (
            select(StorageEntryModel.id)
            .where(StorageEntryModel.id == root_id)
            .cte("updated_subtree", recursive=True)
        )
        tree = tree.union_all(
            select(StorageEntryModel.id).join(
                tree,
                StorageEntryModel.parent_id == tree.c.id,
            )
        )
        values: dict[str, datetime | None] = {"deleted_at": deleted_at}
        if updated_at is not None:
            values["updated_at"] = updated_at
        statement = (
            update(StorageEntryModel)
            .where(StorageEntryModel.id.in_(select(tree.c.id)))
            .values(**values)
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return result.rowcount

    async def _flush(self) -> None:
        try:
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    @staticmethod
    def _entry_model(entry: StorageEntry) -> StorageEntryModel:
        return StorageEntryModel(
            id=entry.id,
            owner_id=entry.owner_id,
            parent_id=entry.parent_id,
            entry_type=(
                EntryType.FOLDER if isinstance(entry, Folder) else EntryType.FILE
            ).value,
            name=entry.name,
            normalized_name=entry.normalized_name,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            deleted_at=entry.deleted_at,
        )

    @staticmethod
    def _to_entry(
        model: StorageEntryModel,
        file_model: FileMetadataModel | None,
    ) -> Folder | File:
        if model.entry_type == EntryType.FOLDER.value:
            return Folder(
                id=model.id,
                owner_id=model.owner_id,
                parent_id=model.parent_id,
                name=model.name,
                normalized_name=model.normalized_name,
                created_at=model.created_at,
                updated_at=model.updated_at,
                deleted_at=model.deleted_at,
            )
        if file_model is None:
            raise PersistenceError("File metadata is missing.")
        return File(
            id=model.id,
            owner_id=model.owner_id,
            parent_id=model.parent_id,
            name=model.name,
            normalized_name=model.normalized_name,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            original_name=file_model.original_name,
            internal_name=file_model.internal_name,
            size=file_model.size,
            mime_type=file_model.mime_type,
            extension=file_model.extension,
            checksum_sha256=file_model.checksum_sha256,
            current_version_number=file_model.current_version_number,
        )

    @staticmethod
    def _version_model(version: FileVersion) -> FileVersionModel:
        return FileVersionModel(
            id=version.id,
            file_id=version.file_id,
            storage_object_id=version.storage_object_id,
            version_number=version.version_number,
            original_name=version.original_name,
            size=version.size,
            mime_type=version.mime_type,
            extension=version.extension,
            checksum_sha256=version.checksum_sha256,
            created_by=version.created_by,
            created_at=version.created_at,
        )

    @staticmethod
    def _to_version(model: FileVersionModel) -> FileVersion:
        return FileVersion(
            id=model.id,
            file_id=model.file_id,
            storage_object_id=model.storage_object_id,
            version_number=model.version_number,
            original_name=model.original_name,
            size=model.size,
            mime_type=model.mime_type,
            extension=model.extension,
            checksum_sha256=model.checksum_sha256,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_trash(model: TrashItemModel) -> TrashItem:
        return TrashItem(
            id=model.id,
            entry_id=model.entry_id,
            original_parent_id=model.original_parent_id,
            deleted_by=model.deleted_by,
            trashed_at=model.trashed_at,
        )
