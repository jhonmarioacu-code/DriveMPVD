from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID, uuid4

from app.application.dtos.auth import AuthPolicyDTO, BootstrapAdminCommandDTO
from app.application.ports.auth_services import (
    Clock,
    PasswordHasher,
    SecretTokenProvider,
)
from app.application.ports.identifiers import IdGenerator
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.auth.bootstrap_admin import BootstrapAdminUseCase
from app.domain.auth.entities import AdminAccount, SecurityEvent
from app.domain.storage.entities import Folder


class FakeAdminAccounts:
    async def get_single(self, *, for_update: bool = False) -> AdminAccount | None:
        assert for_update
        return None

    async def add(self, account: AdminAccount) -> None:
        self.account = account


class FakeStorage:
    def __init__(self) -> None:
        self.folder: Folder | None = None

    async def add_folder(self, folder: Folder) -> None:
        self.folder = folder


class FakeSecurityEvents:
    async def add(self, event: SecurityEvent) -> None:
        self.event = event


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.admin_accounts = FakeAdminAccounts()
        self.storage = FakeStorage()
        self.security_events = FakeSecurityEvents()
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class FakeUnitOfWorkFactory:
    def __init__(self, unit_of_work: FakeUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def __call__(self) -> FakeUnitOfWork:
        return self._unit_of_work


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        assert password == "correct horse battery staple"
        return "password-hash"


class FakeIds:
    def __init__(self) -> None:
        self._values = iter((uuid4(), uuid4(), uuid4()))

    def new(self) -> UUID:
        return next(self._values)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 18, 18, tzinfo=UTC)


class FakeSecrets:
    def fingerprint(self, value: str) -> str:
        return f"fingerprint:{value}"


def _policy() -> AuthPolicyDTO:
    return AuthPolicyDTO(
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86_400,
        maximum_failed_logins=5,
        account_lock_seconds=60,
        login_rate_limit=10,
        login_rate_window_seconds=60,
        login_rate_block_seconds=60,
        refresh_rate_limit=10,
        refresh_rate_window_seconds=60,
        refresh_rate_block_seconds=60,
        minimum_password_length=12,
    )


async def test_bootstrap_provisions_the_canonical_storage_root_atomically() -> None:
    unit_of_work = FakeUnitOfWork()
    use_case = BootstrapAdminUseCase(
        unit_of_work_factory=cast(
            UnitOfWorkFactory,
            FakeUnitOfWorkFactory(unit_of_work),
        ),
        password_hasher=cast(PasswordHasher, FakePasswordHasher()),
        id_generator=cast(IdGenerator, FakeIds()),
        clock=cast(Clock, FixedClock()),
        secrets=cast(SecretTokenProvider, FakeSecrets()),
        policy=_policy(),
    )

    account = await use_case.execute(
        BootstrapAdminCommandDTO(
            username=" Admin ", password="correct horse battery staple"
        )
    )

    root = unit_of_work.storage.folder
    assert root is not None
    assert root.owner_id == account.id
    assert root.parent_id is None
    assert root.name == "Drive"
    assert root.normalized_name == "drive"
    assert root.created_at == account.created_at
    assert unit_of_work.committed
