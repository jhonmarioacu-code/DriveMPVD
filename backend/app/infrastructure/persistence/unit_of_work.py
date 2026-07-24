"""SQLAlchemy implementation of the application Unit of Work contract."""

from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.activity_repository import ActivityRepository
from app.application.ports.auth_repositories import (
    AdminAccountRepository,
    AuthSessionRepository,
    SecurityEventRepository,
)
from app.application.ports.identifiers import IdGenerator
from app.application.ports.outbox_repository import OutboxRepository
from app.application.ports.storage_repository import StorageRepository
from app.infrastructure.exceptions import PersistenceError, UnitOfWorkStateError
from app.infrastructure.persistence.repositories.activity import (
    SQLAlchemyActivityRepository,
)
from app.infrastructure.persistence.repositories.auth import (
    SQLAlchemyAdminAccountRepository,
    SQLAlchemyAuthSessionRepository,
    SQLAlchemySecurityEventRepository,
)
from app.infrastructure.persistence.repositories.outbox import (
    SQLAlchemyOutboxRepository,
)
from app.infrastructure.persistence.repositories.storage import (
    SQLAlchemyStorageRepository,
)


class SQLAlchemyUnitOfWork:
    """Own exactly one AsyncSession and one explicit atomic transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        id_generator: IdGenerator,
    ) -> None:
        self._session_factory = session_factory
        self._id_generator = id_generator
        self._session: AsyncSession | None = None
        self._outbox: SQLAlchemyOutboxRepository | None = None
        self._admin_accounts: SQLAlchemyAdminAccountRepository | None = None
        self._auth_sessions: SQLAlchemyAuthSessionRepository | None = None
        self._security_events: SQLAlchemySecurityEventRepository | None = None
        self._activity: SQLAlchemyActivityRepository | None = None
        self._storage: SQLAlchemyStorageRepository | None = None
        self._completed = False

    @property
    def outbox(self) -> OutboxRepository:
        """Return the repository bound to the active transaction."""
        if self._outbox is None or self._completed:
            raise UnitOfWorkStateError()
        return self._outbox

    @property
    def admin_accounts(self) -> AdminAccountRepository:
        if self._admin_accounts is None or self._completed:
            raise UnitOfWorkStateError()
        return self._admin_accounts

    @property
    def auth_sessions(self) -> AuthSessionRepository:
        if self._auth_sessions is None or self._completed:
            raise UnitOfWorkStateError()
        return self._auth_sessions

    @property
    def security_events(self) -> SecurityEventRepository:
        if self._security_events is None or self._completed:
            raise UnitOfWorkStateError()
        return self._security_events

    @property
    def activity(self) -> ActivityRepository:
        if self._activity is None or self._completed:
            raise UnitOfWorkStateError()
        return self._activity

    @property
    def storage(self) -> StorageRepository:
        if self._storage is None or self._completed:
            raise UnitOfWorkStateError()
        return self._storage

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        """Open a session and begin a transaction explicitly."""
        if self._session is not None:
            raise UnitOfWorkStateError("A Unit of Work cannot be entered twice.")
        self._session = self._session_factory()
        try:
            await self._session.begin()
        except SQLAlchemyError as exc:
            await self._session.close()
            self._session = None
            raise PersistenceError() from exc
        self._outbox = SQLAlchemyOutboxRepository(
            self._session,
            self._id_generator,
        )
        self._admin_accounts = SQLAlchemyAdminAccountRepository(self._session)
        self._auth_sessions = SQLAlchemyAuthSessionRepository(self._session)
        self._security_events = SQLAlchemySecurityEventRepository(self._session)
        self._activity = SQLAlchemyActivityRepository(self._session)
        self._storage = SQLAlchemyStorageRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Rollback unfinished work and always release the session."""
        del exc_value, traceback
        session = self._require_session()
        try:
            if not self._completed:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._outbox = None
            self._admin_accounts = None
            self._auth_sessions = None
            self._security_events = None
            self._activity = None
            self._storage = None
            self._completed = True

    async def commit(self) -> None:
        """Commit all repository writes as one atomic transaction."""
        session = self._require_active_session()
        try:
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            self._completed = True
            raise PersistenceError() from exc
        self._completed = True

    async def rollback(self) -> None:
        """Explicitly discard every write in the current transaction."""
        session = self._require_active_session()
        try:
            await session.rollback()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        finally:
            self._completed = True

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise UnitOfWorkStateError()
        return self._session

    def _require_active_session(self) -> AsyncSession:
        session = self._require_session()
        if self._completed:
            raise UnitOfWorkStateError("The transaction has already completed.")
        return session


class SQLAlchemyUnitOfWorkFactory:
    """Create a fresh SQLAlchemy Unit of Work per use case."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        id_generator: IdGenerator,
    ) -> None:
        self._session_factory = session_factory
        self._id_generator = id_generator

    def __call__(self) -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(self._session_factory, self._id_generator)
