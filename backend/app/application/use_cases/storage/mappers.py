"""Map storage domain entities to stable application read DTOs."""

from app.application.dtos.storage import (
    FileDetailsDTO,
    StorageEntryDTO,
    StorageEntryKind,
    TrashItemDTO,
)
from app.domain.storage.entities import File, Folder, StorageEntry, TrashItem


def entry_to_dto(entry: StorageEntry, *, is_favorite: bool = False) -> StorageEntryDTO:
    if isinstance(entry, File):
        return StorageEntryDTO(
            id=entry.id,
            parent_id=entry.parent_id,
            kind=StorageEntryKind.FILE,
            name=entry.name,
            size=entry.size,
            mime_type=entry.mime_type,
            extension=entry.extension,
            checksum_sha256=entry.checksum_sha256,
            current_version_number=entry.current_version_number,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            is_favorite=is_favorite,
        )
    if not isinstance(entry, Folder):
        raise TypeError("Unsupported storage entry type.")
    return StorageEntryDTO(
        id=entry.id,
        parent_id=entry.parent_id,
        kind=StorageEntryKind.FOLDER,
        name=entry.name,
        size=None,
        mime_type=None,
        extension=None,
        checksum_sha256=None,
        current_version_number=None,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        is_favorite=is_favorite,
    )


def file_to_details_dto(file: File) -> FileDetailsDTO:
    if file.parent_id is None:
        raise TypeError("A file must have a parent folder.")
    return FileDetailsDTO(
        id=file.id,
        parent_id=file.parent_id,
        name=file.name,
        original_name=file.original_name,
        size=file.size,
        mime_type=file.mime_type,
        extension=file.extension,
        checksum_sha256=file.checksum_sha256,
        current_version_number=file.current_version_number,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )


def trash_to_dto(item: TrashItem) -> TrashItemDTO:
    return TrashItemDTO(
        id=item.id,
        entry_id=item.entry_id,
        original_parent_id=item.original_parent_id,
        trashed_at=item.trashed_at,
    )
