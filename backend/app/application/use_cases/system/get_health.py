"""Health query use case."""

from app.application.dtos.system import HealthStatusDTO


class GetHealthUseCase:
    """Return process health without depending on an HTTP framework."""

    def __init__(self, *, service_name: str, version: str) -> None:
        self._service_name = service_name
        self._version = version

    async def execute(self) -> HealthStatusDTO:
        """Build the current liveness result."""
        return HealthStatusDTO(
            status="ok",
            service=self._service_name,
            version=self._version,
        )
