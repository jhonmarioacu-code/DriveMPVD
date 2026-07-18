"""Typed data transfer objects used by application boundaries."""

from app.application.dtos.common import PageDTO, PageRequestDTO
from app.application.dtos.outbox import (
    NewOutboxMessageDTO,
    OutboxCursorDTO,
    OutboxFilterDTO,
    OutboxMessageDTO,
    OutboxPageDTO,
)
from app.application.dtos.system import HealthStatusDTO, ReadinessStatusDTO

__all__ = [
    "HealthStatusDTO",
    "NewOutboxMessageDTO",
    "OutboxCursorDTO",
    "OutboxFilterDTO",
    "OutboxMessageDTO",
    "OutboxPageDTO",
    "PageDTO",
    "PageRequestDTO",
    "ReadinessStatusDTO",
]
