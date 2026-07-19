"""Non-HTTP bootstrap of the singleton administrator."""

from app.application.dtos.auth import AuthPolicyDTO, BootstrapAdminCommandDTO
from app.application.exceptions import ApplicationValidationError, ConflictError
from app.application.ports.auth_services import (
    Clock,
    PasswordHasher,
    SecretTokenProvider,
)
from app.application.ports.identifiers import IdGenerator
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.auth.helpers import (
    create_security_event,
    normalize_username,
)
from app.domain.auth.entities import AdminAccount
from app.domain.auth.enums import SecurityEventType
from app.domain.storage.entities import Folder
from app.domain.storage.value_objects import EntryName


class BootstrapAdminUseCase:
    """Create exactly one administrator outside the public API."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        password_hasher: PasswordHasher,
        id_generator: IdGenerator,
        clock: Clock,
        secrets: SecretTokenProvider,
        policy: AuthPolicyDTO,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._id_generator = id_generator
        self._clock = clock
        self._secrets = secrets
        self._policy = policy

    async def execute(self, command: BootstrapAdminCommandDTO) -> AdminAccount:
        """Create the singleton or fail without replacing existing credentials."""
        normalized_username = normalize_username(command.username)
        if not normalized_username:
            raise ApplicationValidationError("Administrator username is required.")
        if not 1 <= len(normalized_username) <= 100:
            raise ApplicationValidationError("Administrator username is invalid.")
        if not self._policy.minimum_password_length <= len(command.password) <= 1024:
            raise ApplicationValidationError(
                "Administrator password does not meet the minimum length."
            )
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            if await unit_of_work.admin_accounts.get_single(for_update=True):
                raise ConflictError("The administrator account already exists.")
            account = AdminAccount(
                id=self._id_generator.new(),
                username=command.username.strip(),
                normalized_username=normalized_username,
                password_hash=self._password_hasher.hash(command.password),
                enabled=True,
                failed_login_attempts=0,
                locked_until=None,
                password_changed_at=now,
                last_login_at=None,
                created_at=now,
                updated_at=now,
            )
            await unit_of_work.admin_accounts.add(account)
            root_name = EntryName.create("Drive")
            await unit_of_work.storage.add_folder(
                Folder(
                    id=self._id_generator.new(),
                    owner_id=account.id,
                    parent_id=None,
                    name=root_name.value,
                    normalized_name=root_name.normalized,
                    created_at=now,
                    updated_at=now,
                )
            )
            await unit_of_work.security_events.add(
                create_security_event(
                    self._id_generator,
                    self._secrets,
                    event_type=SecurityEventType.ADMIN_CREATED,
                    occurred_at=now,
                    client_ip="local-bootstrap",
                    user_agent="cli",
                    admin_id=account.id,
                )
            )
            await unit_of_work.commit()
        return account
