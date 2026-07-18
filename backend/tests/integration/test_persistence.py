from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import NewOutboxMessageDTO, OutboxFilterDTO
from app.application.ports.identifiers import IdGenerator
from app.infrastructure.exceptions import PersistenceError
from app.infrastructure.persistence import Database, SQLAlchemyUnitOfWorkFactory
from app.infrastructure.persistence.health import SQLAlchemyDatabaseHealthProvider
from app.infrastructure.persistence.identifiers import Uuid7Generator

pytestmark = pytest.mark.postgresql


class StaticIdGenerator(IdGenerator):
    def __init__(self, identifier: UUID) -> None:
        self._identifier = identifier

    def new(self) -> UUID:
        return self._identifier


def _message(
    *,
    aggregate_id: UUID | None = None,
    event_type: str = "catalog.entry.created",
    occurred_at: datetime | None = None,
) -> NewOutboxMessageDTO:
    return NewOutboxMessageDTO(
        aggregate_id=aggregate_id or uuid4(),
        aggregate_type="catalog.entry",
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(UTC),
        payload={"revision": 1},
    )


def _factory(
    database: Database,
    id_generator: IdGenerator | None = None,
) -> SQLAlchemyUnitOfWorkFactory:
    return SQLAlchemyUnitOfWorkFactory(
        database.session_factory,
        id_generator or Uuid7Generator(),
    )


async def test_migration_targets_postgresql_16_and_creates_documented_indexes(
    database: Database,
    clean_outbox: None,
) -> None:
    del clean_outbox
    async with database.engine.connect() as connection:
        version = await connection.scalar(text("SHOW server_version"))
        revision = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
        indexes = await connection.scalars(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND tablename = 'outbox_events'"
            )
        )

    assert str(version).startswith("16.")
    assert revision == "20260718_0002"
    assert set(indexes) == {
        "pk_outbox_events",
        "ix_outbox_events_pending_created_id",
        "ix_outbox_events_aggregate_created_id",
        "ix_outbox_events_type_created_id",
        "ix_outbox_events_deleted_at",
    }


async def test_unit_of_work_commit_and_rollback_are_atomic(
    database: Database,
    clean_outbox: None,
) -> None:
    del clean_outbox
    factory = _factory(database)
    committed_id: UUID
    failed_ids: list[UUID] = []

    async with factory() as unit_of_work:
        committed = await unit_of_work.outbox.add(_message())
        committed_id = committed.id
        await unit_of_work.commit()

    async with factory() as unit_of_work:
        rolled_back = await unit_of_work.outbox.add(_message())
        await unit_of_work.rollback()

    async def fail_transaction() -> None:
        async with factory() as unit_of_work:
            failed = await unit_of_work.outbox.add(_message())
            failed_ids.append(failed.id)
            raise RuntimeError("force atomic rollback")

    with pytest.raises(RuntimeError):
        await fail_transaction()

    async with factory() as unit_of_work:
        assert await unit_of_work.outbox.get(committed_id) is not None
        assert await unit_of_work.outbox.get(rolled_back.id) is None
        assert await unit_of_work.outbox.get(failed_ids[0]) is None


async def test_repository_filters_and_paginates_with_stable_keyset(
    database: Database,
    clean_outbox: None,
) -> None:
    del clean_outbox
    factory = _factory(database)
    aggregate_id = uuid4()
    created_ids: list[UUID] = []

    async with factory() as unit_of_work:
        for index in range(5):
            event_type = "catalog.entry.created" if index < 4 else "catalog.entry.moved"
            persisted = await unit_of_work.outbox.add(
                _message(aggregate_id=aggregate_id, event_type=event_type)
            )
            created_ids.append(persisted.id)
        await unit_of_work.commit()

    filters = OutboxFilterDTO(
        aggregate_id=aggregate_id,
        event_type="catalog.entry.created",
        created_from=datetime.now(UTC) - timedelta(minutes=1),
        created_to=datetime.now(UTC) + timedelta(minutes=1),
    )
    async with factory() as unit_of_work:
        first_page = await unit_of_work.outbox.list(
            filters=filters,
            page=PageRequestDTO(limit=2),
        )
        second_page = await unit_of_work.outbox.list(
            filters=filters,
            page=PageRequestDTO(limit=2),
            cursor=first_page.next_cursor,
        )

    assert [message.id for message in first_page.items] == created_ids[:2]
    assert first_page.next_cursor is not None
    assert [message.id for message in second_page.items] == created_ids[2:4]
    assert second_page.next_cursor is None


async def test_repository_soft_delete_is_idempotent_and_hidden_from_reads(
    database: Database,
    clean_outbox: None,
) -> None:
    del clean_outbox
    factory = _factory(database)
    async with factory() as unit_of_work:
        persisted = await unit_of_work.outbox.add(_message())
        await unit_of_work.commit()

    deleted_at = datetime.now(UTC)
    async with factory() as unit_of_work:
        assert await unit_of_work.outbox.soft_delete(
            persisted.id,
            deleted_at=deleted_at,
        )
        assert not await unit_of_work.outbox.soft_delete(
            persisted.id,
            deleted_at=deleted_at,
        )
        await unit_of_work.commit()

    async with factory() as unit_of_work:
        assert await unit_of_work.outbox.get(persisted.id) is None
        page = await unit_of_work.outbox.list(
            filters=OutboxFilterDTO(),
            page=PageRequestDTO(limit=10),
        )
        assert page.items == ()


async def test_database_rejects_non_uuid7_primary_keys(
    database: Database,
    clean_outbox: None,
) -> None:
    del clean_outbox
    factory = _factory(database, StaticIdGenerator(uuid4()))

    with pytest.raises(PersistenceError):
        async with factory() as unit_of_work:
            await unit_of_work.outbox.add(_message())


async def test_database_health_provider_executes_real_statement(
    database: Database,
) -> None:
    health = SQLAlchemyDatabaseHealthProvider(database.session_factory)

    assert await health.is_ready()
