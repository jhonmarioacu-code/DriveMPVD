"""Failures produced by external systems and infrastructure adapters."""

from typing import ClassVar


class InfrastructureError(Exception):
    """Expected infrastructure failure with a safe public message."""

    code: ClassVar[str] = "infrastructure.unavailable"
    default_message: ClassVar[str] = "A required service is temporarily unavailable."

    def __init__(self, message: str | None = None) -> None:
        self.public_message = message or self.default_message
        super().__init__(self.public_message)


class PersistenceError(InfrastructureError):
    """Database operation failed without exposing driver details."""

    code = "infrastructure.persistence_error"
    default_message = "The database operation could not be completed."


class UnitOfWorkStateError(InfrastructureError):
    """Unit of Work was used outside its valid lifecycle."""

    code = "infrastructure.unit_of_work_state"
    default_message = "The transaction is not in a valid state."


class FileStorageError(InfrastructureError):
    code = "infrastructure.file_storage_error"
    default_message = "The file storage operation could not be completed."
