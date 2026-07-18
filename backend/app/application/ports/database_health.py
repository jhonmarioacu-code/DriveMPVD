"""Database availability port."""

from typing import Protocol


class DatabaseHealthProvider(Protocol):
    """Check the persistence dependency without exposing SQL."""

    async def is_ready(self) -> bool:
        """Return whether PostgreSQL can execute a minimal statement."""
        ...
