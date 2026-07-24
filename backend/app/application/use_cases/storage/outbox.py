"""Reliable cleanup of storage objects through the transactional outbox."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import (
    NewOutboxMessageDTO,
    OutboxFilterDTO,
    OutboxMessageDTO,
    ProcessStorageOutboxCommandDTO,
    ProcessStorageOutboxResultDTO,
)
from app.application.exceptions import ApplicationValidationError, OutboxProcessingError
from app.application.ports.auth_services import Clock
from app.application.ports.file_storage import FileStorageProvider, StorageKey
from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

ORPHAN_SWEEP_REQUESTED_EVENT = "storage.orphan_sweep_requested"
OBJECT_DELETE_REQUESTED_EVENT = "storage.object_delete_requested"


@dataclass(frozen=True, slots=True)
class _EventOutcome:
    """Internal accounting for exactly one leased outbox event."""

    claimed: bool
    processed: bool = False
    deferred: bool = False
    failed: bool = False
    metadata_objects_deleted: int = 0
    physical_objects_deleted: int = 0


class ProcessStorageOutboxUseCase:
    """Detach orphan metadata before scheduling idempotent physical deletion.

    The ordering is deliberate. The database row is conditionally deleted and
    its physical-delete request is inserted atomically. A later retry may call
    the idempotent storage delete more than once, but it can never remove bytes
    that a committed database reference still needs.
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        storage: FileStorageProvider,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._storage = storage
        self._clock = clock

    async def execute(
        self,
        command: ProcessStorageOutboxCommandDTO,
    ) -> ProcessStorageOutboxResultDTO:
        """Run one bounded polling cycle without starving physical cleanup."""
        events_seen = 0
        events_processed = 0
        events_deferred = 0
        events_failed = 0
        metadata_objects_deleted = 0
        physical_objects_deleted = 0

        for _ in range(command.event_batch_size):
            message = await self._next_pending_message()
            if message is None:
                break
            outcome = await self._process_message(message, command)
            if not outcome.claimed:
                # Another worker owns the oldest available event. Stop rather
                # than repeatedly selecting the same skipped-locked row.
                break
            events_seen += 1
            events_processed += int(outcome.processed)
            events_deferred += int(outcome.deferred)
            events_failed += int(outcome.failed)
            metadata_objects_deleted += outcome.metadata_objects_deleted
            physical_objects_deleted += outcome.physical_objects_deleted
            if outcome.failed:
                # Retry after the configured poll interval, not in a tight loop.
                break

        return ProcessStorageOutboxResultDTO(
            events_seen=events_seen,
            events_processed=events_processed,
            events_deferred=events_deferred,
            events_failed=events_failed,
            metadata_objects_deleted=metadata_objects_deleted,
            physical_objects_deleted=physical_objects_deleted,
        )

    async def _next_pending_message(self) -> OutboxMessageDTO | None:
        """Prioritize reclaiming detached bytes before scheduling more work."""
        for event_type in (
            OBJECT_DELETE_REQUESTED_EVENT,
            ORPHAN_SWEEP_REQUESTED_EVENT,
        ):
            async with self._unit_of_work_factory() as unit_of_work:
                page = await unit_of_work.outbox.list(
                    filters=OutboxFilterDTO(event_type=event_type),
                    page=PageRequestDTO(limit=1),
                )
            if page.items:
                return page.items[0]
        return None

    async def _process_message(
        self,
        message: OutboxMessageDTO,
        command: ProcessStorageOutboxCommandDTO,
    ) -> _EventOutcome:
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                leased = await unit_of_work.outbox.get_pending_for_update(
                    message.id,
                    skip_locked=True,
                )
                if leased is None:
                    return _EventOutcome(claimed=False)
                if leased.event_type == ORPHAN_SWEEP_REQUESTED_EVENT:
                    return await self._process_orphan_sweep(
                        unit_of_work,
                        leased,
                        orphan_batch_size=command.orphan_batch_size,
                    )
                if leased.event_type == OBJECT_DELETE_REQUESTED_EVENT:
                    return await self._process_object_delete(unit_of_work, leased)
                raise OutboxProcessingError(
                    "The storage outbox event type is unsupported."
                )
        except Exception as exc:
            await self._record_failure(message.id, error_kind=type(exc).__name__)
            return _EventOutcome(claimed=True, failed=True)

    async def _process_orphan_sweep(
        self,
        unit_of_work: UnitOfWork,
        message: OutboxMessageDTO,
        *,
        orphan_batch_size: int,
    ) -> _EventOutcome:
        objects, has_more = await unit_of_work.storage.claim_orphan_storage_objects(
            limit=orphan_batch_size
        )
        metadata_objects_deleted = 0
        for storage_object in objects:
            if not await unit_of_work.storage.delete_claimed_orphan_storage_object(
                storage_object.id
            ):
                # A concurrent valid reference won the race. No physical event
                # is created, so its bytes remain intact.
                continue
            await unit_of_work.outbox.add(
                NewOutboxMessageDTO(
                    aggregate_id=storage_object.id,
                    aggregate_type="storage.object",
                    event_type=OBJECT_DELETE_REQUESTED_EVENT,
                    occurred_at=self._clock.now(),
                    payload={"storage_key": storage_object.storage_key},
                )
            )
            metadata_objects_deleted += 1

        if has_more:
            await unit_of_work.commit()
            return _EventOutcome(
                claimed=True,
                deferred=True,
                metadata_objects_deleted=metadata_objects_deleted,
            )

        if not await unit_of_work.outbox.mark_processed(
            message.id,
            processed_at=self._clock.now(),
        ):
            raise OutboxProcessingError("The leased storage outbox event was lost.")
        await unit_of_work.commit()
        return _EventOutcome(
            claimed=True,
            processed=True,
            metadata_objects_deleted=metadata_objects_deleted,
        )

    async def _process_object_delete(
        self,
        unit_of_work: UnitOfWork,
        message: OutboxMessageDTO,
    ) -> _EventOutcome:
        storage_key = self._storage_key_from_payload(message)
        await self._storage.delete(storage_key)
        if not await unit_of_work.outbox.mark_processed(
            message.id,
            processed_at=self._clock.now(),
        ):
            raise OutboxProcessingError("The leased storage outbox event was lost.")
        await unit_of_work.commit()
        return _EventOutcome(
            claimed=True,
            processed=True,
            physical_objects_deleted=1,
        )

    async def _record_failure(self, message_id: UUID, *, error_kind: str) -> None:
        """Record a safe category after the failed processing transaction rolls back."""
        async with self._unit_of_work_factory() as unit_of_work:
            recorded = await unit_of_work.outbox.record_failure(
                message_id,
                attempted_at=self._clock.now(),
                error_kind=error_kind,
            )
            if recorded:
                await unit_of_work.commit()

    @staticmethod
    def _storage_key_from_payload(message: OutboxMessageDTO) -> StorageKey:
        value = message.payload.get("storage_key")
        if not isinstance(value, str) or not value or len(value) > 500:
            raise ApplicationValidationError("Storage outbox payload is invalid.")
        logical_path = PurePosixPath(value)
        if (
            logical_path.is_absolute()
            or ".." in logical_path.parts
            or not logical_path.parts
            or logical_path.parts[0] != "objects"
        ):
            raise ApplicationValidationError("Storage outbox payload is invalid.")
        return StorageKey(value)
