"""Application DTOs for per-account favorites and recent opens."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.dtos.storage import StorageEntryDTO


@dataclass(frozen=True, slots=True)
class ActivityEntryDTO:
    """An active storage entry ordered by a user activity timestamp."""

    entry: StorageEntryDTO
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ActivityCursorDTO:
    """Typed keyset cursor used by activity lists."""

    occurred_at: datetime
    entry_id: UUID


@dataclass(frozen=True, slots=True)
class ListActivityQueryDTO:
    owner_id: UUID
    limit: int
    cursor: str | None


@dataclass(frozen=True, slots=True)
class FavoriteStatusDTO:
    entry_id: UUID
    is_favorite: bool


@dataclass(frozen=True, slots=True)
class RecordRecentOpenCommandDTO:
    owner_id: UUID
    entry_id: UUID
