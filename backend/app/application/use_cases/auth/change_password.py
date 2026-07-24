"""Local administrator password rotation with session revocation."""

from app.application.dtos.auth import AuthPolicyDTO, ChangeAdminPasswordCommandDTO
from app.application.exceptions import (
    ApplicationValidationError,
    ResourceNotFoundError,
)
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
from app.domain.auth.enums import SecurityEventType, SessionRevocationReason


class ChangeAdminPasswordUseCase:
    """Rotate the singleton credential outside the public HTTP surface."""

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

    async def execute(self, command: ChangeAdminPasswordCommandDTO) -> AdminAccount:
        """Change the credential atomically and invalidate every active session."""
        normalized_username = normalize_username(command.username)
        if not normalized_username:
            raise ApplicationValidationError("Administrator username is required.")
        if not self._policy.minimum_password_length <= len(command.password) <= 1024:
            raise ApplicationValidationError(
                "Administrator password does not meet the minimum length."
            )

        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            account = await unit_of_work.admin_accounts.get_single(for_update=True)
            if account is None or account.normalized_username != normalized_username:
                raise ResourceNotFoundError("The administrator account was not found.")
            account.change_password(
                password_hash=self._password_hasher.hash(command.password),
                now=now,
            )
            await unit_of_work.admin_accounts.save(account)
            revoked_sessions = await unit_of_work.auth_sessions.revoke_all_active(
                admin_id=account.id,
                now=now,
                reason=SessionRevocationReason.PASSWORD_CHANGED,
            )
            await unit_of_work.security_events.add(
                create_security_event(
                    self._id_generator,
                    self._secrets,
                    event_type=SecurityEventType.ADMIN_PASSWORD_CHANGED,
                    occurred_at=now,
                    client_ip="local-administration",
                    user_agent="cli",
                    admin_id=account.id,
                    details={"revoked_sessions": revoked_sessions},
                )
            )
            await unit_of_work.commit()
        return account
