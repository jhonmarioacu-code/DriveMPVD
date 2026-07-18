"""System UTC clock adapter."""

from datetime import UTC, datetime


class SystemClock:
    """Provide timezone-aware current time."""

    def now(self) -> datetime:
        return datetime.now(UTC)
