"""Pydantic contracts for private favorites and recent opens."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.presentation.schemas.storage import StorageEntryData, StorageModel


class ActivityListQuery(StorageModel):
    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


class ActivityEntryData(StorageModel):
    entry: StorageEntryData
    occurred_at: datetime


class ActivityEntriesData(StorageModel):
    items: tuple[ActivityEntryData, ...]


class FavoriteStatusData(StorageModel):
    entry_id: UUID
    is_favorite: bool


class RecentOpenData(StorageModel):
    entry_id: UUID
