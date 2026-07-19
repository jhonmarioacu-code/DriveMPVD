"""Read-only storage use cases with opaque keyset pagination."""

import base64
import binascii
import json
import unicodedata
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.dtos.common import PageDTO
from app.application.dtos.storage import (
    FileDetailsDTO,
    ListFolderEntriesQueryDTO,
    SortDirection,
    StorageEntryDTO,
    StorageListFiltersDTO,
    StoragePageCursorDTO,
    StorageSortField,
)
from app.application.exceptions import (
    ApplicationValidationError,
    StorageEntryNotFoundError,
)
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.storage.mappers import entry_to_dto, file_to_details_dto
from app.domain.storage.entities import File
from app.domain.storage.value_objects import EntryName


class ListFolderEntriesUseCase:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        query: ListFolderEntriesQueryDTO,
    ) -> PageDTO[StorageEntryDTO]:
        if not 1 <= query.limit <= 200:
            raise ApplicationValidationError("Page limit must be between 1 and 200.")
        filters = _normalized_filters(query.filters)
        _validate_filters(filters)
        cursor = _decode_cursor(query.cursor, query.sort_by, query.direction)
        async with self._unit_of_work_factory() as unit_of_work:
            folder = await unit_of_work.storage.get_folder(query.folder_id)
            if folder is None or folder.owner_id != query.owner_id:
                raise StorageEntryNotFoundError()
            entries, has_more = await unit_of_work.storage.list_children(
                owner_id=query.owner_id,
                parent_id=query.folder_id,
                limit=query.limit,
                filters=filters,
                sort_by=query.sort_by,
                direction=query.direction,
                cursor=cursor,
            )
        items = tuple(entry_to_dto(entry) for entry in entries)
        next_cursor = None
        if has_more and items:
            next_cursor = _encode_cursor(items[-1], query.sort_by, query.direction)
        return PageDTO(items=items, next_cursor=next_cursor)


class GetFileDetailsUseCase:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(self, *, owner_id: UUID, file_id: UUID) -> FileDetailsDTO:
        async with self._unit_of_work_factory() as unit_of_work:
            entry = await unit_of_work.storage.get_entry(file_id)
        if not isinstance(entry, File) or entry.owner_id != owner_id:
            raise StorageEntryNotFoundError()
        return file_to_details_dto(entry)


class GetFolderNavigationUseCase:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        owner_id: UUID,
        folder_id: UUID | None,
    ) -> tuple[StorageEntryDTO, ...]:
        async with self._unit_of_work_factory() as unit_of_work:
            path = await unit_of_work.storage.get_folder_path(
                owner_id=owner_id,
                folder_id=folder_id,
            )
        if not path:
            raise StorageEntryNotFoundError()
        return tuple(entry_to_dto(folder) for folder in path)


def _validate_filters(filters: StorageListFiltersDTO) -> None:
    if filters.minimum_size is not None and filters.minimum_size < 0:
        raise ApplicationValidationError("Minimum size cannot be negative.")
    if filters.maximum_size is not None and filters.maximum_size < 0:
        raise ApplicationValidationError("Maximum size cannot be negative.")
    if (
        filters.minimum_size is not None
        and filters.maximum_size is not None
        and filters.minimum_size > filters.maximum_size
    ):
        raise ApplicationValidationError("Minimum size cannot exceed maximum size.")
    if (
        filters.modified_from is not None
        and filters.modified_to is not None
        and filters.modified_from > filters.modified_to
    ):
        raise ApplicationValidationError(
            "Modified-from cannot be later than modified-to."
        )


def _normalized_filters(filters: StorageListFiltersDTO) -> StorageListFiltersDTO:
    name = filters.name_contains
    normalized_name = (
        unicodedata.normalize("NFKC", name).strip().casefold() if name else None
    )
    extension = filters.extension
    normalized_extension = (
        extension.strip().removeprefix(".").casefold() if extension else None
    )
    return StorageListFiltersDTO(
        name_contains=normalized_name or None,
        kind=filters.kind,
        extension=normalized_extension or None,
        minimum_size=filters.minimum_size,
        maximum_size=filters.maximum_size,
        modified_from=filters.modified_from,
        modified_to=filters.modified_to,
    )


def _sort_key(entry: StorageEntryDTO, sort_by: StorageSortField) -> str:
    if sort_by is StorageSortField.NAME:
        return EntryName.create(entry.name).normalized
    if sort_by is StorageSortField.DATE:
        return entry.updated_at.isoformat()
    if sort_by is StorageSortField.SIZE:
        return str(entry.size if entry.size is not None else -1)
    return entry.kind.value


def _encode_cursor(
    entry: StorageEntryDTO,
    sort_by: StorageSortField,
    direction: SortDirection,
) -> str:
    payload = {
        "v": 1,
        "sort": sort_by.value,
        "direction": direction.value,
        "key": _sort_key(entry, sort_by),
        "id": str(entry.id),
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(serialized).decode().rstrip("=")


def _decode_cursor(
    value: str | None,
    sort_by: StorageSortField,
    direction: SortDirection,
) -> StoragePageCursorDTO | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded: Any = json.loads(base64.urlsafe_b64decode(value + padding))
        if not isinstance(decoded, dict):
            raise ValueError
        if (
            decoded.get("v") != 1
            or decoded.get("sort") != sort_by.value
            or decoded.get("direction") != direction.value
            or not isinstance(decoded.get("key"), str)
            or not isinstance(decoded.get("id"), str)
        ):
            raise ValueError
        cursor = StoragePageCursorDTO(
            sort_key=decoded["key"],
            entry_id=UUID(decoded["id"]),
        )
        if sort_by is StorageSortField.DATE:
            datetime.fromisoformat(cursor.sort_key)
        elif sort_by is StorageSortField.SIZE:
            int(cursor.sort_key)
        return cursor
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ApplicationValidationError("The pagination cursor is invalid.") from exc
