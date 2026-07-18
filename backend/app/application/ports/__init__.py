"""Interfaces implemented by infrastructure adapters."""

from app.application.ports.database_health import DatabaseHealthProvider
from app.application.ports.file_storage import FileStorageProvider
from app.application.ports.identifiers import IdGenerator
from app.application.ports.outbox_repository import OutboxRepository
from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "DatabaseHealthProvider",
    "FileStorageProvider",
    "IdGenerator",
    "OutboxRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
