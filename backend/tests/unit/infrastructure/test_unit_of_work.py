from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.exceptions import PersistenceError, UnitOfWorkStateError
from app.infrastructure.persistence.identifiers import Uuid7Generator
from app.infrastructure.persistence.unit_of_work import SQLAlchemyUnitOfWork


class SessionMock:
    def __init__(self) -> None:
        self.begin = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.close = AsyncMock()


def _unit_of_work(session: SessionMock) -> SQLAlchemyUnitOfWork:
    sqlalchemy_session = cast(AsyncSession, session)
    factory = cast(
        async_sessionmaker[AsyncSession],
        Mock(return_value=sqlalchemy_session),
    )
    return SQLAlchemyUnitOfWork(factory, Uuid7Generator())


def _session() -> SessionMock:
    return SessionMock()


async def test_unit_of_work_commits_and_closes_one_transaction() -> None:
    session = _session()
    unit_of_work = _unit_of_work(session)

    async with unit_of_work:
        assert unit_of_work.outbox is not None
        assert unit_of_work.storage is not None
        await unit_of_work.commit()

    session.begin.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()

    with pytest.raises(UnitOfWorkStateError):
        _ = unit_of_work.outbox


async def test_unit_of_work_rolls_back_uncommitted_and_failed_blocks() -> None:
    first_session = _session()
    first = _unit_of_work(first_session)
    async with first:
        pass
    first_session.rollback.assert_awaited_once()

    second_session = _session()
    second = _unit_of_work(second_session)
    with pytest.raises(RuntimeError):
        async with second:
            raise RuntimeError("use case failed")
    second_session.rollback.assert_awaited_once()


async def test_unit_of_work_supports_explicit_rollback() -> None:
    session = _session()
    unit_of_work = _unit_of_work(session)

    async with unit_of_work:
        await unit_of_work.rollback()

    session.rollback.assert_awaited_once()
    with pytest.raises(UnitOfWorkStateError):
        await unit_of_work.commit()


async def test_unit_of_work_wraps_begin_commit_and_rollback_failures() -> None:
    begin_session = _session()
    begin_session.begin.side_effect = SQLAlchemyError("begin")
    with pytest.raises(PersistenceError):
        async with _unit_of_work(begin_session):
            pass
    begin_session.close.assert_awaited_once()

    commit_session = _session()
    commit_session.commit.side_effect = SQLAlchemyError("commit")
    commit_unit = _unit_of_work(commit_session)
    with pytest.raises(PersistenceError):
        async with commit_unit:
            await commit_unit.commit()
    commit_session.rollback.assert_awaited()

    rollback_session = _session()
    rollback_session.rollback.side_effect = SQLAlchemyError("rollback")
    rollback_unit = _unit_of_work(rollback_session)
    with pytest.raises(PersistenceError):
        async with rollback_unit:
            await rollback_unit.rollback()


async def test_unit_of_work_rejects_invalid_lifecycle_operations() -> None:
    session = _session()
    unit_of_work = _unit_of_work(session)

    with pytest.raises(UnitOfWorkStateError):
        await unit_of_work.commit()

    await unit_of_work.__aenter__()
    with pytest.raises(UnitOfWorkStateError):
        await unit_of_work.__aenter__()
    await unit_of_work.__aexit__(None, None, None)
