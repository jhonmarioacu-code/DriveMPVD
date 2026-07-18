"""The only dependency composition root."""

from dataclasses import dataclass

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.system import GetHealthUseCase, GetReadinessUseCase
from app.infrastructure.config import Settings
from app.infrastructure.persistence import Database, SQLAlchemyUnitOfWorkFactory
from app.infrastructure.persistence.health import SQLAlchemyDatabaseHealthProvider
from app.infrastructure.persistence.identifiers import Uuid7Generator


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Fully constructed application services exposed to presentation."""

    get_health: GetHealthUseCase
    get_readiness: GetReadinessUseCase
    unit_of_work_factory: UnitOfWorkFactory
    database: Database

    @classmethod
    def build(cls, settings: Settings) -> "ApplicationContainer":
        """Create use cases and inject all configuration/adapters."""
        database = Database(settings)
        id_generator = Uuid7Generator()
        database_health = SQLAlchemyDatabaseHealthProvider(database.session_factory)
        return cls(
            get_health=GetHealthUseCase(
                service_name=settings.app_name,
                version=settings.app_version,
            ),
            get_readiness=GetReadinessUseCase(database_health),
            unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(
                database.session_factory,
                id_generator,
            ),
            database=database,
        )
