"""SQLAlchemy implementation of the outbox repository port."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import (
    NewOutboxMessageDTO,
    OutboxCursorDTO,
    OutboxFilterDTO,
    OutboxMessageDTO,
    OutboxPageDTO,
)
from app.application.ports.identifiers import IdGenerator
from app.infrastructure.exceptions import PersistenceError
from app.infrastructure.persistence.models.outbox import OutboxEventModel
from app.shared.json_types import JsonObject


class SQLAlchemyOutboxRepository:
    """Map ORM rows to DTOs and never commit its owning transaction."""

    def __init__(self, session: AsyncSession, id_generator: IdGenerator) -> None:
        self._session = session
        self._id_generator = id_generator

    async def add(self, message: NewOutboxMessageDTO) -> OutboxMessageDTO:
        """Stage and flush one UUID7 outbox row."""
        model = OutboxEventModel(
            id=self._id_generator.new(),
            aggregate_id=message.aggregate_id,
            aggregate_type=message.aggregate_type,
            event_type=message.event_type,
            occurred_at=message.occurred_at,
            payload=dict(message.payload),
        )
        self._session.add(model)
        try:
            await self._session.flush()
            await self._session.refresh(model)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return self._to_dto(model)

    async def get(self, message_id: UUID) -> OutboxMessageDTO | None:
        """Return one non-deleted row without loading relationships."""
        statement = select(OutboxEventModel).where(
            OutboxEventModel.id == message_id,
            OutboxEventModel.deleted_at.is_(None),
        )
        try:
            model = await self._session.scalar(statement)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if model is None else self._to_dto(model)

    async def list(
        self,
        *,
        filters: OutboxFilterDTO,
        page: PageRequestDTO,
        cursor: OutboxCursorDTO | None = None,
    ) -> OutboxPageDTO:
        """Execute one filtered keyset query capped at limit plus one."""
        statement = self._filtered_statement(filters)
        if cursor is not None:
            statement = statement.where(
                or_(
                    OutboxEventModel.created_at > cursor.created_at,
                    and_(
                        OutboxEventModel.created_at == cursor.created_at,
                        OutboxEventModel.id > cursor.id,
                    ),
                )
            )
        statement = statement.order_by(
            OutboxEventModel.created_at,
            OutboxEventModel.id,
        ).limit(page.limit + 1)
        try:
            result = await self._session.scalars(statement)
            models = list(result.all())
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

        has_more = len(models) > page.limit
        visible_models = models[: page.limit]
        items = tuple(self._to_dto(model) for model in visible_models)
        next_cursor = None
        if has_more and visible_models:
            last = visible_models[-1]
            next_cursor = OutboxCursorDTO(created_at=last.created_at, id=last.id)
        return OutboxPageDTO(items=items, next_cursor=next_cursor)

    async def soft_delete(self, message_id: UUID, *, deleted_at: datetime) -> bool:
        """Mark one active row as deleted without committing the Unit of Work."""
        statement = (
            update(OutboxEventModel)
            .where(
                OutboxEventModel.id == message_id,
                OutboxEventModel.deleted_at.is_(None),
            )
            .values(deleted_at=deleted_at, updated_at=deleted_at)
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return bool(result.rowcount)

    @staticmethod
    def _filtered_statement(
        filters: OutboxFilterDTO,
    ) -> Select[tuple[OutboxEventModel]]:
        statement = select(OutboxEventModel).where(
            OutboxEventModel.deleted_at.is_(None)
        )
        if filters.pending_only:
            statement = statement.where(OutboxEventModel.processed_at.is_(None))
        if filters.event_type is not None:
            statement = statement.where(
                OutboxEventModel.event_type == filters.event_type
            )
        if filters.aggregate_id is not None:
            statement = statement.where(
                OutboxEventModel.aggregate_id == filters.aggregate_id
            )
        if filters.created_from is not None:
            statement = statement.where(
                OutboxEventModel.created_at >= filters.created_from
            )
        if filters.created_to is not None:
            statement = statement.where(
                OutboxEventModel.created_at <= filters.created_to
            )
        return statement

    @staticmethod
    def _to_dto(model: OutboxEventModel) -> OutboxMessageDTO:
        return OutboxMessageDTO(
            id=model.id,
            aggregate_id=model.aggregate_id,
            aggregate_type=model.aggregate_type,
            event_type=model.event_type,
            occurred_at=model.occurred_at,
            payload=cast(JsonObject, dict(model.payload)),
            attempts=model.attempts,
            processed_at=model.processed_at,
            last_error=model.last_error,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )
