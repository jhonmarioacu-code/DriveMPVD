from dataclasses import replace
from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID, uuid4

import pytest

from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import (
    NewOutboxMessageDTO,
    OutboxCursorDTO,
    OutboxFilterDTO,
    OutboxMessageDTO,
    OutboxPageDTO,
    ProcessStorageOutboxCommandDTO,
)
from app.application.exceptions import ApplicationValidationError
from app.application.ports.file_storage import FileStorageProvider, StorageKey
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.storage.outbox import (
    OBJECT_DELETE_REQUESTED_EVENT,
    ORPHAN_SWEEP_REQUESTED_EVENT,
    ProcessStorageOutboxUseCase,
)
from app.domain.storage.entities import StorageObject
from app.domain.storage.enums import StorageObjectStatus
from app.infrastructure.exceptions import FileStorageError
from app.shared.json_types import JsonObject

NOW = datetime(2026, 7, 19, 12, tzinfo=UTC)
CHECKSUM = "a" * 64


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeOutbox:
    def __init__(self, events: tuple[OutboxMessageDTO, ...] = ()) -> None:
        self.events = {event.id: event for event in events}
        self.order = [event.id for event in events]
        self.locked_ids: set[UUID] = set()

    async def add(self, message: NewOutboxMessageDTO) -> OutboxMessageDTO:
        event = OutboxMessageDTO(
            id=uuid4(),
            aggregate_id=message.aggregate_id,
            aggregate_type=message.aggregate_type,
            event_type=message.event_type,
            occurred_at=message.occurred_at,
            payload=message.payload,
            attempts=0,
            processed_at=None,
            last_error=None,
            created_at=NOW,
            updated_at=NOW,
            deleted_at=None,
        )
        self.events[event.id] = event
        self.order.append(event.id)
        return event

    async def list(
        self,
        *,
        filters: OutboxFilterDTO,
        page: PageRequestDTO,
        cursor: OutboxCursorDTO | None = None,
    ) -> OutboxPageDTO:
        del cursor
        items = tuple(
            event
            for event_id in self.order
            if (event := self.events[event_id]).deleted_at is None
            and (not filters.pending_only or event.processed_at is None)
            and (filters.event_type is None or event.event_type == filters.event_type)
        )
        return OutboxPageDTO(items=items[: page.limit], next_cursor=None)

    async def get_pending_for_update(
        self,
        message_id: UUID,
        *,
        skip_locked: bool,
    ) -> OutboxMessageDTO | None:
        del skip_locked
        if message_id in self.locked_ids:
            return None
        event = self.events[message_id]
        if event.processed_at is not None or event.deleted_at is not None:
            return None
        return event

    async def mark_processed(self, message_id: UUID, *, processed_at: datetime) -> bool:
        event = self.events[message_id]
        if event.processed_at is not None or event.deleted_at is not None:
            return False
        self.events[message_id] = replace(
            event,
            attempts=event.attempts + 1,
            processed_at=processed_at,
            last_error=None,
            updated_at=processed_at,
        )
        return True

    async def record_failure(
        self,
        message_id: UUID,
        *,
        attempted_at: datetime,
        error_kind: str,
    ) -> bool:
        event = self.events[message_id]
        if event.processed_at is not None or event.deleted_at is not None:
            return False
        self.events[message_id] = replace(
            event,
            attempts=event.attempts + 1,
            last_error=error_kind[:120],
            updated_at=attempted_at,
        )
        return True


class FakeStorageRepository:
    def __init__(self, objects: tuple[StorageObject, ...] = ()) -> None:
        self.objects = {storage_object.id: storage_object for storage_object in objects}
        self.reference_wins: set[UUID] = set()

    async def claim_orphan_storage_objects(
        self,
        *,
        limit: int,
    ) -> tuple[tuple[StorageObject, ...], bool]:
        candidates = tuple(self.objects.values())
        return candidates[:limit], len(candidates) > limit

    async def delete_claimed_orphan_storage_object(self, object_id: UUID) -> bool:
        if object_id in self.reference_wins:
            return False
        return self.objects.pop(object_id, None) is not None


class FakeFileStorage:
    def __init__(self) -> None:
        self.deleted: list[StorageKey] = []
        self.fail = False

    async def delete(self, key: StorageKey) -> None:
        if self.fail:
            raise FileStorageError()
        self.deleted.append(key)


class FakeUnitOfWork:
    def __init__(
        self,
        outbox: FakeOutbox,
        storage: FakeStorageRepository,
    ) -> None:
        self.outbox = outbox
        self.storage = storage
        self.commits = 0

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
        self.commits += 1


class FakeUnitOfWorkFactory:
    def __init__(self, outbox: FakeOutbox, storage: FakeStorageRepository) -> None:
        self._outbox = outbox
        self._storage = storage
        self.created: list[FakeUnitOfWork] = []

    def __call__(self) -> FakeUnitOfWork:
        unit_of_work = FakeUnitOfWork(self._outbox, self._storage)
        self.created.append(unit_of_work)
        return unit_of_work


def _event(
    event_type: str,
    *,
    aggregate_id: UUID | None = None,
    payload: JsonObject | None = None,
) -> OutboxMessageDTO:
    return OutboxMessageDTO(
        id=uuid4(),
        aggregate_id=aggregate_id or uuid4(),
        aggregate_type="storage.entry",
        event_type=event_type,
        occurred_at=NOW,
        payload=payload or {},
        attempts=0,
        processed_at=None,
        last_error=None,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )


def _storage_object() -> StorageObject:
    object_id = uuid4()
    return StorageObject(
        id=object_id,
        storage_key=f"objects/{object_id}",
        size=1,
        mime_type="application/octet-stream",
        checksum_sha256=CHECKSUM,
        status=StorageObjectStatus.READY,
        created_at=NOW,
        updated_at=NOW,
    )


def _use_case(
    outbox: FakeOutbox,
    storage: FakeStorageRepository,
    file_storage: FakeFileStorage,
) -> ProcessStorageOutboxUseCase:
    return ProcessStorageOutboxUseCase(
        unit_of_work_factory=cast(
            UnitOfWorkFactory,
            FakeUnitOfWorkFactory(outbox, storage),
        ),
        storage=cast(FileStorageProvider, file_storage),
        clock=FixedClock(),
    )


async def test_orphan_sweep_detaches_metadata_then_deletes_physical_bytes() -> None:
    object_to_delete = _storage_object()
    sweep = _event(ORPHAN_SWEEP_REQUESTED_EVENT)
    outbox = FakeOutbox((sweep,))
    storage = FakeStorageRepository((object_to_delete,))
    file_storage = FakeFileStorage()

    result = await _use_case(outbox, storage, file_storage).execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=4, orphan_batch_size=10)
    )

    assert result.events_seen == 2
    assert result.events_processed == 2
    assert result.events_deferred == 0
    assert result.events_failed == 0
    assert result.metadata_objects_deleted == 1
    assert result.physical_objects_deleted == 1
    assert storage.objects == {}
    assert file_storage.deleted == [StorageKey(object_to_delete.storage_key)]
    assert all(event.processed_at == NOW for event in outbox.events.values())
    delete_events = [
        event
        for event in outbox.events.values()
        if event.event_type == OBJECT_DELETE_REQUESTED_EVENT
    ]
    assert len(delete_events) == 1
    assert delete_events[0].payload == {"storage_key": object_to_delete.storage_key}


async def test_orphan_sweep_defers_until_all_metadata_is_detached() -> None:
    first = _storage_object()
    second = _storage_object()
    sweep = _event(ORPHAN_SWEEP_REQUESTED_EVENT)
    outbox = FakeOutbox((sweep,))
    storage = FakeStorageRepository((first, second))
    file_storage = FakeFileStorage()

    result = await _use_case(outbox, storage, file_storage).execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=1, orphan_batch_size=1)
    )

    assert result.events_seen == 1
    assert result.events_processed == 0
    assert result.events_deferred == 1
    assert result.metadata_objects_deleted == 1
    assert first.id not in storage.objects
    assert second.id in storage.objects
    assert outbox.events[sweep.id].processed_at is None
    assert not file_storage.deleted


async def test_physical_delete_failure_is_recorded_and_retried_idempotently() -> None:
    object_to_delete = _storage_object()
    event = _event(
        OBJECT_DELETE_REQUESTED_EVENT,
        aggregate_id=object_to_delete.id,
        payload={"storage_key": object_to_delete.storage_key},
    )
    outbox = FakeOutbox((event,))
    storage = FakeStorageRepository()
    file_storage = FakeFileStorage()
    file_storage.fail = True
    use_case = _use_case(outbox, storage, file_storage)

    failed = await use_case.execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=2, orphan_batch_size=1)
    )

    assert failed.events_seen == 1
    assert failed.events_failed == 1
    assert outbox.events[event.id].attempts == 1
    assert outbox.events[event.id].last_error == "FileStorageError"
    assert outbox.events[event.id].processed_at is None

    file_storage.fail = False
    retried = await use_case.execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=2, orphan_batch_size=1)
    )

    assert retried.events_processed == 1
    assert file_storage.deleted == [StorageKey(object_to_delete.storage_key)]
    assert outbox.events[event.id].attempts == 2
    assert outbox.events[event.id].last_error is None
    assert outbox.events[event.id].processed_at == NOW


async def test_outbox_stops_when_another_worker_has_leased_the_event() -> None:
    event = _event(ORPHAN_SWEEP_REQUESTED_EVENT)
    outbox = FakeOutbox((event,))
    outbox.locked_ids.add(event.id)

    result = await _use_case(
        outbox,
        FakeStorageRepository(),
        FakeFileStorage(),
    ).execute(ProcessStorageOutboxCommandDTO(event_batch_size=2, orphan_batch_size=1))

    assert result.events_seen == 0
    assert outbox.events[event.id].processed_at is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"storage_key": ""},
        {"storage_key": "/objects/file"},
        {"storage_key": "objects/../file"},
        {"storage_key": "staging/file"},
    ],
)
def test_object_delete_payload_rejects_unsafe_keys(payload: JsonObject) -> None:
    with pytest.raises(ApplicationValidationError):
        ProcessStorageOutboxUseCase._storage_key_from_payload(
            _event(OBJECT_DELETE_REQUESTED_EVENT, payload=payload)
        )


@pytest.mark.parametrize(
    ("event_batch_size", "orphan_batch_size"),
    [(0, 1), (201, 1), (1, 0), (1, 1_001)],
)
def test_outbox_command_rejects_unbounded_work(
    event_batch_size: int,
    orphan_batch_size: int,
) -> None:
    with pytest.raises(ApplicationValidationError):
        ProcessStorageOutboxCommandDTO(
            event_batch_size=event_batch_size,
            orphan_batch_size=orphan_batch_size,
        )
