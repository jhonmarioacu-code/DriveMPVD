from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID, uuid4

import pytest

from app.application.dtos.activity import (
    ActivityCursorDTO,
    ActivityEntryDTO,
    ListActivityQueryDTO,
    RecordRecentOpenCommandDTO,
)
from app.application.exceptions import (
    ApplicationValidationError,
    StorageEntryNotFoundError,
)
from app.application.ports.activity_repository import ActivityRecord
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.activity import (
    ListActivityUseCase,
    RecordRecentOpenUseCase,
    RemoveFavoriteUseCase,
    SetFavoriteUseCase,
    _decode_cursor,
    _encode_cursor,
)
from app.application.use_cases.storage.mappers import entry_to_dto
from app.domain.storage.entities import Folder, StorageEntry


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeStorage:
    def __init__(self, entries: dict[UUID, StorageEntry]) -> None:
        self._entries = entries
        self.locked_entry_ids: list[UUID] = []

    async def get_entry(
        self,
        entry_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> StorageEntry | None:
        del include_deleted
        if for_update:
            self.locked_entry_ids.append(entry_id)
        return self._entries.get(entry_id)


class FakeActivity:
    def __init__(self, records: tuple[ActivityRecord, ...] = ()) -> None:
        self.records = records
        self.favorite_ids: set[UUID] = set()
        self.recorded_opens: list[tuple[UUID, UUID, datetime]] = []

    async def favorite_entry_ids(
        self,
        *,
        owner_id: UUID,
        entry_ids: tuple[UUID, ...],
    ) -> frozenset[UUID]:
        del owner_id
        return frozenset(
            entry_id for entry_id in entry_ids if entry_id in self.favorite_ids
        )

    async def add_favorite(
        self,
        *,
        owner_id: UUID,
        entry_id: UUID,
        created_at: datetime,
    ) -> bool:
        del owner_id, created_at
        existed = entry_id in self.favorite_ids
        self.favorite_ids.add(entry_id)
        return not existed

    async def remove_favorite(self, *, owner_id: UUID, entry_id: UUID) -> bool:
        del owner_id
        existed = entry_id in self.favorite_ids
        self.favorite_ids.discard(entry_id)
        return existed

    async def record_recent_open(
        self,
        *,
        owner_id: UUID,
        entry_id: UUID,
        opened_at: datetime,
    ) -> None:
        self.recorded_opens.append((owner_id, entry_id, opened_at))

    async def list_favorites(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: ActivityCursorDTO | None,
    ) -> tuple[tuple[ActivityRecord, ...], bool]:
        del owner_id, cursor
        return self.records[:limit], len(self.records) > limit

    async def list_recents(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: ActivityCursorDTO | None,
    ) -> tuple[tuple[ActivityRecord, ...], bool]:
        del owner_id, cursor
        return self.records[:limit], len(self.records) > limit


class FakeUnitOfWork:
    def __init__(self, storage: FakeStorage, activity: FakeActivity) -> None:
        self.storage = storage
        self.activity = activity
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    async def commit(self) -> None:
        self.committed = True


class FakeUnitOfWorkFactory:
    def __init__(self, unit_of_work: FakeUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def __call__(self) -> FakeUnitOfWork:
        return self._unit_of_work


def _folder(entry_id: UUID, owner_id: UUID, name: str = "Documents") -> Folder:
    now = datetime(2026, 7, 20, 12, tzinfo=UTC)
    return Folder(
        id=entry_id,
        owner_id=owner_id,
        parent_id=None,
        name=name,
        normalized_name=name.casefold(),
        created_at=now,
        updated_at=now,
    )


def _factory(
    entry: StorageEntry,
    activity: FakeActivity | None = None,
) -> tuple[FakeUnitOfWork, UnitOfWorkFactory]:
    unit_of_work = FakeUnitOfWork(
        FakeStorage({entry.id: entry}),
        activity or FakeActivity(),
    )
    return unit_of_work, cast(UnitOfWorkFactory, FakeUnitOfWorkFactory(unit_of_work))


async def test_favorite_commands_verify_ownership_are_idempotent_and_commit() -> None:
    owner_id = uuid4()
    entry = _folder(uuid4(), owner_id)
    unit_of_work, factory = _factory(entry)
    clock = FixedClock(datetime(2026, 7, 20, 12, tzinfo=UTC))

    added = await SetFavoriteUseCase(factory, clock).execute(
        owner_id=owner_id,
        entry_id=entry.id,
    )
    assert added.is_favorite is True
    assert entry.id in unit_of_work.activity.favorite_ids
    assert unit_of_work.storage.locked_entry_ids == [entry.id]
    assert unit_of_work.committed

    removed = await RemoveFavoriteUseCase(factory, clock).execute(
        owner_id=owner_id,
        entry_id=entry.id,
    )
    assert removed.is_favorite is False
    assert entry.id not in unit_of_work.activity.favorite_ids

    with pytest.raises(StorageEntryNotFoundError):
        await SetFavoriteUseCase(factory, clock).execute(
            owner_id=uuid4(),
            entry_id=entry.id,
        )


async def test_recent_command_records_explicit_owned_open() -> None:
    owner_id = uuid4()
    entry = _folder(uuid4(), owner_id)
    unit_of_work, factory = _factory(entry)
    now = datetime(2026, 7, 20, 12, tzinfo=UTC)

    await RecordRecentOpenUseCase(factory, FixedClock(now)).execute(
        RecordRecentOpenCommandDTO(owner_id=owner_id, entry_id=entry.id)
    )

    assert unit_of_work.activity.recorded_opens == [(owner_id, entry.id, now)]
    assert unit_of_work.committed


async def test_activity_list_maps_favorites_and_emits_a_bound_cursor() -> None:
    owner_id = uuid4()
    first = _folder(uuid4(), owner_id, "First")
    second = _folder(uuid4(), owner_id, "Second")
    now = datetime(2026, 7, 20, 12, tzinfo=UTC)
    records = (
        ActivityRecord(first, now, True),
        ActivityRecord(second, now - timedelta(seconds=1), False),
    )
    unit_of_work, factory = _factory(first, FakeActivity(records))
    use_case = ListActivityUseCase(
        factory,
        FixedClock(now),
        kind="favorites",
    )

    page = await use_case.execute(
        ListActivityQueryDTO(owner_id=owner_id, limit=1, cursor=None)
    )

    assert [item.entry.name for item in page.items] == ["First"]
    assert page.items[0].entry.is_favorite is True
    assert page.next_cursor is not None
    assert _decode_cursor(page.next_cursor, "favorites") == ActivityCursorDTO(
        occurred_at=now,
        entry_id=first.id,
    )
    assert unit_of_work.committed is False


def test_activity_cursor_rejects_malformed_or_cross_feed_values() -> None:
    entry = _folder(uuid4(), uuid4())
    now = datetime(2026, 7, 20, 12, tzinfo=UTC)
    cursor = _encode_cursor(
        ActivityEntryDTO(entry=entry_to_dto(entry), occurred_at=now),
        "recents",
    )
    assert _decode_cursor(cursor, "recents") == ActivityCursorDTO(now, entry.id)
    with pytest.raises(ApplicationValidationError):
        _decode_cursor(cursor, "favorites")
    with pytest.raises(ApplicationValidationError):
        _decode_cursor("not-a-cursor", "recents")
