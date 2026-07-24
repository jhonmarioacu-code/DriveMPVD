import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.infrastructure.config.settings import AppEnvironment, Settings
from app.infrastructure.persistence import Database


def _test_database_url() -> str:
    url = os.getenv("DRIVEMPVD_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DRIVEMPVD_TEST_DATABASE_URL is required for PostgreSQL tests")
    return url


@pytest.fixture(scope="session")
def migrated_database_url() -> Iterator[str]:
    """Prove downgrade/upgrade reproducibility before repository tests."""
    url = _test_database_url()
    config = Config("alembic.ini")
    config.attributes["database_url"] = url

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    yield url
    command.downgrade(config, "base")


@pytest.fixture
async def database(migrated_database_url: str) -> AsyncIterator[Database]:
    settings = Settings(
        environment=AppEnvironment.TEST,
        database_url=migrated_database_url,
        storage_root=Path.cwd().anchor,
        database_pool_size=2,
        database_max_overflow=0,
    )
    persistence = Database(settings)
    yield persistence
    await persistence.dispose()


@pytest.fixture
async def clean_outbox(database: Database) -> AsyncIterator[None]:
    async with database.engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE outbox_events"))
    yield
    async with database.engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE outbox_events"))


@pytest.fixture
async def clean_auth(database: Database) -> AsyncIterator[None]:
    statement = text(
        "TRUNCATE TABLE security_events, auth_sessions, auth_rate_limits, "
        "admin_accounts CASCADE"
    )
    async with database.engine.begin() as connection:
        await connection.execute(statement)
    yield
    async with database.engine.begin() as connection:
        await connection.execute(statement)


@pytest.fixture
async def clean_storage(database: Database) -> AsyncIterator[None]:
    statement = text(
        "TRUNCATE TABLE recent_opens, favorites, thumbnails, previews, "
        "upload_sessions, trash_items, "
        "file_versions, file_metadata, storage_entries, storage_objects, "
        "security_events, auth_sessions, auth_rate_limits, admin_accounts, "
        "outbox_events CASCADE"
    )
    async with database.engine.begin() as connection:
        await connection.execute(statement)
    yield
    async with database.engine.begin() as connection:
        await connection.execute(statement)
