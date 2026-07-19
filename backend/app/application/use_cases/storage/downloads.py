"""Prepare an authorized immutable file for physical delivery."""

from uuid import UUID

from app.application.dtos.storage import FileDownloadDTO
from app.application.exceptions import StorageEntryNotFoundError
from app.application.ports.file_storage import FileStorageProvider, StorageKey
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.storage.entities import File
from app.domain.storage.enums import StorageObjectStatus


class PrepareFileDownloadUseCase:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        storage: FileStorageProvider,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._storage = storage

    async def execute(self, *, owner_id: UUID, file_id: UUID) -> FileDownloadDTO:
        async with self._unit_of_work_factory() as unit_of_work:
            entry = await unit_of_work.storage.get_entry(file_id)
            if not isinstance(entry, File) or entry.owner_id != owner_id:
                raise StorageEntryNotFoundError()
            version = await unit_of_work.storage.get_current_version(entry.id)
            if version is None:
                raise StorageEntryNotFoundError()
            storage_object = await unit_of_work.storage.get_storage_object(
                version.storage_object_id
            )
        if (
            storage_object is None
            or storage_object.status is not StorageObjectStatus.READY
            or storage_object.deleted_at is not None
        ):
            raise StorageEntryNotFoundError()
        key = StorageKey(storage_object.storage_key)
        physical = await self._storage.stat(key)
        if physical is None or physical.size != entry.size:
            raise StorageEntryNotFoundError()
        return FileDownloadDTO(
            id=entry.id,
            storage_key=key,
            filename=entry.name,
            size=entry.size,
            mime_type=entry.mime_type,
            checksum_sha256=entry.checksum_sha256,
            version_number=entry.current_version_number,
            updated_at=entry.updated_at,
        )
