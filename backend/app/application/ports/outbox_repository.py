"""Repository contract for the transactional outbox."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import (
    NewOutboxMessageDTO,
    OutboxCursorDTO,
    OutboxFilterDTO,
    OutboxMessageDTO,
    OutboxPageDTO,
)


class OutboxRepository(Protocol):
    """Persist and query outbox messages without exposing ORM objects."""

    async def add(self, message: NewOutboxMessageDTO) -> OutboxMessageDTO:
        """Stage a new outbox message in the current transaction."""
        ...

    async def get(self, message_id: UUID) -> OutboxMessageDTO | None:
        """Return one active message by identifier."""
        ...

    async def list(
        self,
        *,
        filters: OutboxFilterDTO,
        page: PageRequestDTO,
        cursor: OutboxCursorDTO | None = None,
    ) -> OutboxPageDTO:
        """Return a filtered keyset page with bounded memory usage."""
        ...

    async def soft_delete(self, message_id: UUID, *, deleted_at: datetime) -> bool:
        """Soft-delete an active message in the current transaction."""
        ...
