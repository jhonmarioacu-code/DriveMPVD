"""Identifier generation port."""

from typing import Protocol
from uuid import UUID


class IdGenerator(Protocol):
    """Generate sortable RFC 9562 UUID version 7 identifiers."""

    def new(self) -> UUID:
        """Return a new UUID version 7."""
        ...
