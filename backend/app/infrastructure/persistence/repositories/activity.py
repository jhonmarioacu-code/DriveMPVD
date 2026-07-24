"""SQLAlchemy implementation of per-account activity projections."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, delete, literal, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.application.dtos.activity import ActivityCursorDTO
from app.application.ports.activity_repository import ActivityRecord
from app.infrastructure.exceptions import PersistenceError
from app.infrastructure.persistence.models.activity import (
    FavoriteModel,
    RecentOpenModel,
)
from app.infrastructure.persistence.models.storage import (
    FileMetadataModel,
    StorageEntryModel,
)
from app.infrastructure.persistence.repositories.storage import (
    storage_entry_from_models,
)


class SQLAlchemyActivityRepository:
    """Query activity through constrained joins to active owned storage entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def favorite_entry_ids(
        self,
        *,
        owner_id: UUID,
        entry_ids: tuple[UUID, ...],
    ) -> frozenset[UUID]:
        if not entry_ids:
            return frozenset()
        statement = select(FavoriteModel.entry_id).where(
            FavoriteModel.owner_id == owner_id,
            FavoriteModel.entry_id.in_(entry_ids),
        )
        try:
            values = (await self._session.scalars(statement)).all()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return frozenset(values)

    async def add_favorite(
        self,
        *,
        owner_id: UUID,
        entry_id: UUID,
        created_at: datetime,
    ) -> bool:
        statement = (
            insert(FavoriteModel)
            .values(owner_id=owner_id, entry_id=entry_id, created_at=created_at)
            .on_conflict_do_nothing(index_elements=["owner_id", "entry_id"])
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return bool(result.rowcount)

    async def remove_favorite(self, *, owner_id: UUID, entry_id: UUID) -> bool:
        statement = delete(FavoriteModel).where(
            FavoriteModel.owner_id == owner_id,
            FavoriteModel.entry_id == entry_id,
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return bool(result.rowcount)

    async def record_recent_open(
        self,
        *,
        owner_id: UUID,
        entry_id: UUID,
        opened_at: datetime,
    ) -> None:
        statement = insert(RecentOpenModel).values(
            owner_id=owner_id,
            entry_id=entry_id,
            opened_at=opened_at,
            open_count=1,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["owner_id", "entry_id"],
            set_={
                "opened_at": opened_at,
                "open_count": RecentOpenModel.open_count + 1,
            },
        )
        try:
            await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    async def list_favorites(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: ActivityCursorDTO | None,
    ) -> tuple[tuple[ActivityRecord, ...], bool]:
        return await self._list_activity(
            owner_id=owner_id,
            limit=limit,
            cursor=cursor,
            source=FavoriteModel,
            occurred_at=FavoriteModel.created_at,
        )

    async def list_recents(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: ActivityCursorDTO | None,
    ) -> tuple[tuple[ActivityRecord, ...], bool]:
        return await self._list_activity(
            owner_id=owner_id,
            limit=limit,
            cursor=cursor,
            source=RecentOpenModel,
            occurred_at=RecentOpenModel.opened_at,
        )

    async def _list_activity(
        self,
        *,
        owner_id: UUID,
        limit: int,
        cursor: ActivityCursorDTO | None,
        source: type[FavoriteModel] | type[RecentOpenModel],
        occurred_at: Any,
    ) -> tuple[tuple[ActivityRecord, ...], bool]:
        favorite = aliased(FavoriteModel)
        favorite_match = and_(
            favorite.owner_id == owner_id,
            favorite.entry_id == StorageEntryModel.id,
        )
        statement = (
            select(
                StorageEntryModel,
                FileMetadataModel,
                occurred_at.label("occurred_at"),
                favorite.entry_id.is_not(None).label("is_favorite"),
            )
            .join(
                source,
                and_(
                    source.owner_id == owner_id, source.entry_id == StorageEntryModel.id
                ),
            )
            .outerjoin(
                FileMetadataModel,
                FileMetadataModel.entry_id == StorageEntryModel.id,
            )
            .outerjoin(favorite, favorite_match)
            .where(
                StorageEntryModel.owner_id == owner_id,
                StorageEntryModel.deleted_at.is_(None),
            )
        )
        if cursor is not None:
            statement = statement.where(
                tuple_(occurred_at, StorageEntryModel.id)
                < tuple_(literal(cursor.occurred_at), literal(cursor.entry_id))
            )
        statement = statement.order_by(
            occurred_at.desc(), StorageEntryModel.id.desc()
        ).limit(limit + 1)
        try:
            rows = (await self._session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        has_more = len(rows) > limit
        records = tuple(
            ActivityRecord(
                entry=storage_entry_from_models(entry_model, file_model),
                occurred_at=timestamp,
                is_favorite=is_favorite,
            )
            for entry_model, file_model, timestamp, is_favorite in rows[:limit]
        )
        return records, has_more
