"""Base exceptions raised by domain rules."""

from typing import ClassVar


class DomainError(Exception):
    """Expected violation of a domain invariant."""

    code: ClassVar[str] = "domain.invariant_violation"
    default_message: ClassVar[str] = "A domain rule was violated."

    def __init__(self, message: str | None = None) -> None:
        self.public_message = message or self.default_message
        super().__init__(self.public_message)
