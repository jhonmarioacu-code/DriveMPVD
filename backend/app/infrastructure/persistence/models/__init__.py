"""SQLAlchemy models; never exported as domain entities."""

from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.models.outbox import OutboxEventModel

__all__ = ["Base", "OutboxEventModel"]
