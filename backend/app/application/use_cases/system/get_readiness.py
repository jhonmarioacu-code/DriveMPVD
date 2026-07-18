"""Readiness query use case."""

from app.application.dtos.system import ReadinessStatusDTO
from app.application.exceptions import DependencyUnavailableError
from app.application.ports.database_health import DatabaseHealthProvider


class GetReadinessUseCase:
    """Verify that required persistence infrastructure is available."""

    def __init__(self, database_health: DatabaseHealthProvider) -> None:
        self._database_health = database_health

    async def execute(self) -> ReadinessStatusDTO:
        """Return readiness or a sanitized infrastructure failure."""
        if not await self._database_health.is_ready():
            raise DependencyUnavailableError("The database is temporarily unavailable.")
        return ReadinessStatusDTO(status="ready", database="available")
