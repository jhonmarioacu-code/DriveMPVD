"""Exceptions describing expected application failures."""

from typing import ClassVar


class ApplicationError(Exception):
    """Base error for a failed use case."""

    code: ClassVar[str] = "application.error"
    default_message: ClassVar[str] = "The operation could not be completed."

    def __init__(self, message: str | None = None) -> None:
        self.public_message = message or self.default_message
        super().__init__(self.public_message)


class ResourceNotFoundError(ApplicationError):
    """Requested resource does not exist or is unavailable."""

    code = "application.resource_not_found"
    default_message = "The requested resource was not found."


class ConflictError(ApplicationError):
    """Requested change conflicts with current state."""

    code = "application.conflict"
    default_message = "The operation conflicts with the current state."


class ApplicationValidationError(ApplicationError):
    """Input is well formed but invalid for the use case."""

    code = "application.validation_error"
    default_message = "The operation contains invalid values."
