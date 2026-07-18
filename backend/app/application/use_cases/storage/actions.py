"""Transactional commands for the logical storage tree."""

from datetime import datetime
from uuid import UUID

from app.application.dtos.outbox import NewOutboxMessageDTO
from app.application.dtos.storage import (
    CopyEntryCommandDTO,
    CreateFolderCommandDTO,
    MoveEntryCommandDTO,
    PermanentDeleteResultDTO,
    PermanentlyDeleteCommandDTO,
    RenameEntryCommandDTO,
    RestoreEntryCommandDTO,
    StorageEntryDTO,
    TrashEntryCommandDTO,
    TrashItemDTO,
)
from app.application.exceptions import (
    StorageEntryNotFoundError,
    StorageNameConflictError,
)
from app.application.ports.auth_services import Clock
from app.application.ports.identifiers import IdGenerator
from app.application.ports.storage_repository import StorageRepository
from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.use_cases.storage.mappers import entry_to_dto, trash_to_dto
from app.domain.storage.entities import (
    File,
    FileVersion,
    Folder,
    StorageEntry,
    TrashItem,
)
from app.domain.storage.exceptions import InvalidMoveError, InvalidStateTransitionError
from app.domain.storage.value_objects import EntryName


class StorageUseCase:
    """Common ownership and collision rules for storage commands."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        id_generator: IdGenerator,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._id_generator = id_generator
        self._clock = clock

    @staticmethod
    def _require_owned(entry: StorageEntry | None, owner_id: UUID) -> StorageEntry:
        if entry is None or entry.owner_id != owner_id:
            raise StorageEntryNotFoundError()
        return entry

    @staticmethod
    def _require_folder(folder: Folder | None, owner_id: UUID) -> Folder:
        if (
            folder is None
            or folder.owner_id != owner_id
            or folder.deleted_at is not None
        ):
            raise StorageEntryNotFoundError()
        return folder

    @staticmethod
    async def _ensure_name_available(
        repository: StorageRepository,
        *,
        parent_id: UUID,
        name: EntryName,
        exclude_entry_id: UUID | None = None,
    ) -> None:
        if await repository.name_exists(
            parent_id=parent_id,
            normalized_name=name.normalized,
            exclude_entry_id=exclude_entry_id,
        ):
            raise StorageNameConflictError()


class CreateFolderUseCase(StorageUseCase):
    async def execute(self, command: CreateFolderCommandDTO) -> StorageEntryDTO:
        now = self._clock.now()
        name = EntryName.create(command.name)
        async with self._unit_of_work_factory() as unit_of_work:
            parent = self._require_folder(
                await unit_of_work.storage.get_folder(
                    command.parent_id,
                    for_update=True,
                ),
                command.owner_id,
            )
            await self._ensure_name_available(
                unit_of_work.storage,
                parent_id=parent.id,
                name=name,
            )
            folder = Folder(
                id=self._id_generator.new(),
                owner_id=command.owner_id,
                parent_id=parent.id,
                name=name.value,
                normalized_name=name.normalized,
                created_at=now,
                updated_at=now,
            )
            await unit_of_work.storage.add_folder(folder)
            await unit_of_work.commit()
        return entry_to_dto(folder)


class RenameEntryUseCase(StorageUseCase):
    async def execute(self, command: RenameEntryCommandDTO) -> StorageEntryDTO:
        now = self._clock.now()
        name = EntryName.create(command.new_name)
        async with self._unit_of_work_factory() as unit_of_work:
            entry = self._require_owned(
                await unit_of_work.storage.get_entry(
                    command.entry_id,
                    for_update=True,
                ),
                command.owner_id,
            )
            if entry.parent_id is None:
                raise InvalidStateTransitionError("The storage root cannot be renamed.")
            await self._ensure_name_available(
                unit_of_work.storage,
                parent_id=entry.parent_id,
                name=name,
                exclude_entry_id=entry.id,
            )
            entry.rename(name, now=now)
            await unit_of_work.storage.save_entry(entry)
            await unit_of_work.commit()
        return entry_to_dto(entry)


class MoveEntryUseCase(StorageUseCase):
    async def execute(self, command: MoveEntryCommandDTO) -> StorageEntryDTO:
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            entry = self._require_owned(
                await unit_of_work.storage.get_entry(
                    command.entry_id,
                    for_update=True,
                ),
                command.owner_id,
            )
            if entry.parent_id is None or entry.id == command.destination_folder_id:
                raise InvalidMoveError()
            destination = self._require_folder(
                await unit_of_work.storage.get_folder(
                    command.destination_folder_id,
                    for_update=True,
                ),
                command.owner_id,
            )
            if isinstance(entry, Folder) and await unit_of_work.storage.is_descendant(
                ancestor_id=entry.id,
                candidate_id=destination.id,
            ):
                raise InvalidMoveError()
            await self._ensure_name_available(
                unit_of_work.storage,
                parent_id=destination.id,
                name=EntryName.create(entry.name),
                exclude_entry_id=entry.id,
            )
            entry.move(destination.id, now=now)
            await unit_of_work.storage.save_entry(entry)
            await unit_of_work.commit()
        return entry_to_dto(entry)


class CopyEntryUseCase(StorageUseCase):
    async def execute(self, command: CopyEntryCommandDTO) -> StorageEntryDTO:
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            source = self._require_owned(
                await unit_of_work.storage.get_entry(command.entry_id),
                command.owner_id,
            )
            if source.parent_id is None:
                raise InvalidStateTransitionError("The storage root cannot be copied.")
            destination = self._require_folder(
                await unit_of_work.storage.get_folder(
                    command.destination_folder_id,
                    for_update=True,
                ),
                command.owner_id,
            )
            target_name = EntryName.create(command.new_name or source.name)
            await self._ensure_name_available(
                unit_of_work.storage,
                parent_id=destination.id,
                name=target_name,
            )
            if isinstance(source, File):
                copied: StorageEntry = await self._copy_file(
                    unit_of_work,
                    source=source,
                    parent_id=destination.id,
                    name=target_name,
                    now=now,
                )
            else:
                if not isinstance(source, Folder):
                    raise InvalidStateTransitionError("Unsupported storage entry type.")
                copied = await self._copy_folder_tree(
                    unit_of_work,
                    source=source,
                    parent_id=destination.id,
                    name=target_name,
                    now=now,
                )
            await unit_of_work.commit()
        return entry_to_dto(copied)

    async def _copy_folder_tree(
        self,
        unit_of_work: UnitOfWork,
        *,
        source: Folder,
        parent_id: UUID,
        name: EntryName,
        now: datetime,
    ) -> Folder:
        copied_root = Folder(
            id=self._id_generator.new(),
            owner_id=source.owner_id,
            parent_id=parent_id,
            name=name.value,
            normalized_name=name.normalized,
            created_at=now,
            updated_at=now,
        )
        await unit_of_work.storage.add_folder(copied_root)
        folder_ids: dict[UUID, UUID] = {source.id: copied_root.id}
        async for node in unit_of_work.storage.stream_subtree(source.id):
            child = node.entry
            if child.id == source.id:
                continue
            if child.parent_id is None or child.parent_id not in folder_ids:
                raise InvalidStateTransitionError("Subtree order is inconsistent.")
            new_parent_id = folder_ids[child.parent_id]
            child_name = EntryName.create(child.name)
            if isinstance(child, Folder):
                copied_folder = Folder(
                    id=self._id_generator.new(),
                    owner_id=child.owner_id,
                    parent_id=new_parent_id,
                    name=child_name.value,
                    normalized_name=child_name.normalized,
                    created_at=now,
                    updated_at=now,
                )
                await unit_of_work.storage.add_folder(copied_folder)
                folder_ids[child.id] = copied_folder.id
            else:
                await self._copy_file(
                    unit_of_work,
                    source=child,
                    parent_id=new_parent_id,
                    name=child_name,
                    now=now,
                )
        return copied_root

    async def _copy_file(
        self,
        unit_of_work: UnitOfWork,
        *,
        source: File,
        parent_id: UUID,
        name: EntryName,
        now: datetime,
    ) -> File:
        version = await unit_of_work.storage.get_current_version(source.id)
        if version is None:
            raise InvalidStateTransitionError("The file has no current version.")
        file_id = self._id_generator.new()
        internal_name = (
            f"{file_id}.{name.extension}" if name.extension else str(file_id)
        )
        copied = File(
            id=file_id,
            owner_id=source.owner_id,
            parent_id=parent_id,
            name=name.value,
            normalized_name=name.normalized,
            original_name=name.value,
            internal_name=internal_name,
            size=source.size,
            mime_type=source.mime_type,
            extension=name.extension,
            checksum_sha256=source.checksum_sha256,
            current_version_number=1,
            created_at=now,
            updated_at=now,
        )
        copied_version = FileVersion(
            id=self._id_generator.new(),
            file_id=file_id,
            storage_object_id=version.storage_object_id,
            version_number=1,
            original_name=name.value,
            size=source.size,
            mime_type=source.mime_type,
            extension=name.extension,
            checksum_sha256=source.checksum_sha256,
            created_by=source.owner_id,
            created_at=now,
        )
        await unit_of_work.storage.add_file(copied, copied_version)
        return copied


class TrashEntryUseCase(StorageUseCase):
    async def execute(self, command: TrashEntryCommandDTO) -> TrashItemDTO:
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            entry = self._require_owned(
                await unit_of_work.storage.get_entry(
                    command.entry_id,
                    include_deleted=True,
                    for_update=True,
                ),
                command.owner_id,
            )
            if entry.deleted_at is not None:
                existing = await unit_of_work.storage.get_trash_item_by_entry(entry.id)
                if existing is None:
                    raise InvalidStateTransitionError()
                return trash_to_dto(existing)
            if entry.parent_id is None:
                raise InvalidStateTransitionError("The storage root cannot be trashed.")
            trash_item = TrashItem(
                id=self._id_generator.new(),
                entry_id=entry.id,
                original_parent_id=entry.parent_id,
                deleted_by=command.owner_id,
                trashed_at=now,
            )
            entry.move_to_trash(now=now)
            await unit_of_work.storage.soft_delete_subtree(entry.id, deleted_at=now)
            await unit_of_work.storage.add_trash_item(trash_item)
            await unit_of_work.commit()
        return trash_to_dto(trash_item)


class RestoreEntryUseCase(StorageUseCase):
    async def execute(self, command: RestoreEntryCommandDTO) -> StorageEntryDTO:
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            trash_item = await unit_of_work.storage.get_trash_item(
                command.trash_item_id,
                for_update=True,
            )
            if trash_item is None or trash_item.deleted_by != command.owner_id:
                raise StorageEntryNotFoundError()
            entry = self._require_owned(
                await unit_of_work.storage.get_entry(
                    trash_item.entry_id,
                    include_deleted=True,
                    for_update=True,
                ),
                command.owner_id,
            )
            destination_id = (
                command.destination_folder_id or trash_item.original_parent_id
            )
            destination = self._require_folder(
                await unit_of_work.storage.get_folder(destination_id, for_update=True),
                command.owner_id,
            )
            await self._ensure_name_available(
                unit_of_work.storage,
                parent_id=destination.id,
                name=EntryName.create(entry.name),
                exclude_entry_id=entry.id,
            )
            entry.restore(parent_id=destination.id, now=now)
            await unit_of_work.storage.save_entry(entry)
            await unit_of_work.storage.restore_subtree(entry.id, restored_at=now)
            await unit_of_work.storage.remove_trash_item(trash_item.id)
            await unit_of_work.commit()
        return entry_to_dto(entry)


class PermanentlyDeleteUseCase(StorageUseCase):
    async def execute(
        self, command: PermanentlyDeleteCommandDTO
    ) -> PermanentDeleteResultDTO:
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            trash_item = await unit_of_work.storage.get_trash_item(
                command.trash_item_id,
                for_update=True,
            )
            if trash_item is None or trash_item.deleted_by != command.owner_id:
                raise StorageEntryNotFoundError()
            entry = self._require_owned(
                await unit_of_work.storage.get_entry(
                    trash_item.entry_id,
                    include_deleted=True,
                    for_update=True,
                ),
                command.owner_id,
            )
            if entry.deleted_at is None:
                raise InvalidStateTransitionError("Only trashed entries can be purged.")
            await unit_of_work.storage.remove_trash_item(trash_item.id)
            deleted_count = await unit_of_work.storage.hard_delete_subtree(entry.id)
            await unit_of_work.outbox.add(
                NewOutboxMessageDTO(
                    aggregate_id=entry.id,
                    aggregate_type="storage.entry",
                    event_type="storage.orphan_sweep_requested",
                    occurred_at=now,
                    payload={"purged_entry_id": str(entry.id)},
                )
            )
            await unit_of_work.commit()
        return PermanentDeleteResultDTO(deleted_entries=deleted_count)
