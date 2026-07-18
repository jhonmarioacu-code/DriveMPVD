"""Repository implementations backed by SQLAlchemy."""

from app.infrastructure.persistence.repositories.outbox import (
    SQLAlchemyOutboxRepository,
)

__all__ = ["SQLAlchemyOutboxRepository"]
