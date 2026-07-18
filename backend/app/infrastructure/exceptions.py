"""Failures produced by external systems and infrastructure adapters."""

from typing import ClassVar


class InfrastructureError(Exception):
    """Expected infrastructure failure with a safe public message."""

    code: ClassVar[str] = "infrastructure.unavailable"
    default_message: ClassVar[str] = "A required service is temporarily unavailable."

    def __init__(self, message: str | None = None) -> None:
        self.public_message = message or self.default_message
        super().__init__(self.public_message)
