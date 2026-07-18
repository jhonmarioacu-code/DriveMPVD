"""Asynchronous SQLAlchemy engine and session factory."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.config import Settings


class Database:
    """Own the process-wide engine while Unit of Work owns each session."""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url.unicode_string(),
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
            echo=settings.database_echo,
            connect_args={
                "server_settings": {
                    "application_name": settings.app_name,
                    "statement_timeout": str(settings.database_statement_timeout_ms),
                    "timezone": "UTC",
                }
            },
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def dispose(self) -> None:
        """Close every pooled database connection during application shutdown."""
        await self.engine.dispose()
