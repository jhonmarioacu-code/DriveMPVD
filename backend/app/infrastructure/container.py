"""The only dependency composition root."""

from dataclasses import dataclass

from app.application.use_cases.system import GetHealthUseCase
from app.infrastructure.config import Settings


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Fully constructed application services exposed to presentation."""

    get_health: GetHealthUseCase

    @classmethod
    def build(cls, settings: Settings) -> "ApplicationContainer":
        """Create use cases and inject all configuration/adapters."""
        return cls(
            get_health=GetHealthUseCase(
                service_name=settings.app_name,
                version=settings.app_version,
            )
        )
