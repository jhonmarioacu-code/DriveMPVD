"""Persistence port for per-account storage activity projections."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dtos.activity import ActivityCursorDTO
from app.domain.storage.entities import StorageEntry


@dataclass(frozen=True, slots=True)
class ActivityRecord:
    """A storage entry and the timestamp that orders it in an activity feed."""

    entry: StorageEntry
    occurred_at: datetime
    is_favorite: bool


class ActivityRepository(Protocol):
    """Keep favorites and recent opens private to their owning account."""

    async def favorite_entry_ids(
        self,
        *,
        owner_id: UUID,
        entry_ids: tuple[UUID, ...],
    ) -> frozenset[UUID]: ...

    async def add_favorite(
        self,
        *,
        owner_id: UUID,
        entry_id: UUID,
        created_at: datetime,
    ) -> bool:
        """Persist an idempotent favorite and report whether it was newly added."""
        ...

    async def remove_favorite(self, *, owner_id: UUID, entry_id: UUID) -> bool:
        """Remove an idempotent favorite and report whether it existed."""
        ...

    async def record_recent_open(
        self,
        *,
        owner_id: UUID,
        entry_id: UUID,
        opened_at: datetime,
    ) -> None:
        """Upsert a recent open without retaining one row per interaction."""
        ...

    async def list_favorites(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: ActivityCursorDTO | None,
    ) -> tuple[tuple[ActivityRecord, ...], bool]: ...

    async def list_recents(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: ActivityCursorDTO | None,
    ) -> tuple[tuple[ActivityRecord, ...], bool]: ...
