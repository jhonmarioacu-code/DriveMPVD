from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.dtos.storage import (
    SortDirection,
    StorageEntryDTO,
    StorageEntryKind,
    StorageListFiltersDTO,
    StorageSortField,
)
from app.application.exceptions import ApplicationValidationError
from app.application.use_cases.storage.queries import (
    _decode_cursor,
    _encode_cursor,
    _normalized_filters,
    _sort_key,
    _validate_filters,
)


def _filters(
    *,
    name_contains: str | None = None,
    kind: StorageEntryKind | None = None,
    extension: str | None = None,
    minimum_size: int | None = None,
    maximum_size: int | None = None,
    modified_from: datetime | None = None,
    modified_to: datetime | None = None,
) -> StorageListFiltersDTO:
    return StorageListFiltersDTO(
        name_contains=name_contains,
        kind=kind,
        extension=extension,
        minimum_size=minimum_size,
        maximum_size=maximum_size,
        modified_from=modified_from,
        modified_to=modified_to,
    )


@pytest.mark.parametrize(
    "filters",
    [
        _filters(minimum_size=-1),
        _filters(maximum_size=-1),
        _filters(minimum_size=2, maximum_size=1),
        _filters(
            modified_from=datetime(2026, 1, 2, tzinfo=UTC),
            modified_to=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ],
)
def test_storage_filters_reject_impossible_ranges(
    filters: StorageListFiltersDTO,
) -> None:
    with pytest.raises(ApplicationValidationError):
        _validate_filters(filters)


def test_storage_filters_normalize_unicode_extension_and_blank_values() -> None:
    normalized = _normalized_filters(
        _filters(name_contains="  F\uff2f\uff2f  ", extension=" .PDF ")
    )
    assert normalized.name_contains == "foo"
    assert normalized.extension == "pdf"
    blank = _normalized_filters(_filters(name_contains="  ", extension=" . "))
    assert blank.name_contains is None
    assert blank.extension is None


def test_cursors_bind_sort_direction_and_typed_sort_key() -> None:
    now = datetime(2026, 7, 19, tzinfo=UTC)
    entry = StorageEntryDTO(
        id=uuid4(),
        parent_id=None,
        kind=StorageEntryKind.FILE,
        name="Report.PDF",
        size=42,
        mime_type="application/pdf",
        extension="pdf",
        checksum_sha256="a" * 64,
        current_version_number=1,
        created_at=now - timedelta(days=1),
        updated_at=now,
    )
    for sort_by in StorageSortField:
        cursor = _encode_cursor(entry, sort_by, SortDirection.ASC)
        decoded = _decode_cursor(cursor, sort_by, SortDirection.ASC)
        assert decoded is not None
        assert decoded.entry_id == entry.id
        assert decoded.sort_key == _sort_key(entry, sort_by)
        with pytest.raises(ApplicationValidationError):
            _decode_cursor(cursor, sort_by, SortDirection.DESC)


@pytest.mark.parametrize("cursor", ["W10", "e30", "not-base64", "eyJ2IjoyfQ"])
def test_cursor_rejects_non_object_or_incomplete_payload(cursor: str) -> None:
    with pytest.raises(ApplicationValidationError):
        _decode_cursor(cursor, StorageSortField.NAME, SortDirection.ASC)
