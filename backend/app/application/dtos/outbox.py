"""Typed application contracts for the transactional outbox."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.exceptions import ApplicationValidationError
from app.shared.json_types import JsonObject


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationValidationError(f"{field_name} must include a timezone.")


@dataclass(frozen=True, slots=True)
class NewOutboxMessageDTO:
    """Event data accepted by the outbox repository before persistence."""

    aggregate_id: UUID
    aggregate_type: str
    event_type: str
    occurred_at: datetime
    payload: JsonObject

    def __post_init__(self) -> None:
        _require_aware(self.occurred_at, "occurred_at")
        if not self.aggregate_type.strip() or not self.event_type.strip():
            raise ApplicationValidationError(
                "aggregate_type and event_type must not be empty."
            )


@dataclass(frozen=True, slots=True)
class OutboxMessageDTO:
    """Persisted outbox message detached from the ORM model."""

    id: UUID
    aggregate_id: UUID
    aggregate_type: str
    event_type: str
    occurred_at: datetime
    payload: JsonObject
    attempts: int
    processed_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class OutboxCursorDTO:
    """Stable keyset cursor ordered by creation time and identifier."""

    created_at: datetime
    id: UUID

    def __post_init__(self) -> None:
        _require_aware(self.created_at, "cursor.created_at")


@dataclass(frozen=True, slots=True)
class OutboxFilterDTO:
    """Supported outbox filters; all can be served by bounded queries."""

    event_type: str | None = None
    aggregate_id: UUID | None = None
    pending_only: bool = True
    created_from: datetime | None = None
    created_to: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_from is not None:
            _require_aware(self.created_from, "created_from")
        if self.created_to is not None:
            _require_aware(self.created_to, "created_to")
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ApplicationValidationError(
                "created_from must not be later than created_to."
            )


@dataclass(frozen=True, slots=True)
class OutboxPageDTO:
    """A bounded outbox page with a typed keyset cursor."""

    items: tuple[OutboxMessageDTO, ...]
    next_cursor: OutboxCursorDTO | None


@dataclass(frozen=True, slots=True)
class ProcessStorageOutboxCommandDTO:
    """Bounded work requested from the storage-outbox consumer."""

    event_batch_size: int
    orphan_batch_size: int

    def __post_init__(self) -> None:
        if not 1 <= self.event_batch_size <= 200:
            raise ApplicationValidationError(
                "event_batch_size must be between 1 and 200."
            )
        if not 1 <= self.orphan_batch_size <= 1_000:
            raise ApplicationValidationError(
                "orphan_batch_size must be between 1 and 1000."
            )


@dataclass(frozen=True, slots=True)
class ProcessStorageOutboxResultDTO:
    """Observable result of one bounded storage-outbox polling cycle."""

    events_seen: int
    events_processed: int
    events_deferred: int
    events_failed: int
    metadata_objects_deleted: int
    physical_objects_deleted: int
