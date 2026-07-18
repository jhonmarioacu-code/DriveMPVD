"""Credential login for the singleton administrator."""

from datetime import datetime, timedelta
from uuid import UUID

from app.application.dtos.auth import (
    AuthenticationResultDTO,
    AuthPolicyDTO,
    LoginCommandDTO,
)
from app.application.exceptions import (
    AccountDisabledError,
    AccountTemporarilyLockedError,
    ApplicationError,
    AuthenticationError,
)
from app.application.ports.auth_repositories import RateLimiter
from app.application.ports.auth_services import (
    Clock,
    JwtProvider,
    PasswordHasher,
    SecretTokenProvider,
)
from app.application.ports.identifiers import IdGenerator
from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.use_cases.auth.helpers import (
    create_security_event,
    enforce_rate_limit,
    normalize_username,
    retry_after_seconds,
)
from app.domain.auth.entities import AuthSession
from app.domain.auth.enums import SecurityEventType
from app.shared.json_types import JsonObject


class LoginUseCase:
    """Authenticate credentials, enforce lockout and create one token family."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        rate_limiter: RateLimiter,
        password_hasher: PasswordHasher,
        jwt_provider: JwtProvider,
        secrets: SecretTokenProvider,
        id_generator: IdGenerator,
        clock: Clock,
        policy: AuthPolicyDTO,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._rate_limiter = rate_limiter
        self._password_hasher = password_hasher
        self._jwt_provider = jwt_provider
        self._secrets = secrets
        self._id_generator = id_generator
        self._clock = clock
        self._policy = policy

    async def execute(self, command: LoginCommandDTO) -> AuthenticationResultDTO:
        """Return a new session or a generic, audited authentication failure."""
        now = self._clock.now()
        normalized_username = normalize_username(command.username)
        await enforce_rate_limit(
            self._rate_limiter,
            scope="auth.login",
            subject=f"{command.client_ip}|{normalized_username}",
            now=now,
            limit=self._policy.login_rate_limit,
            window_seconds=self._policy.login_rate_window_seconds,
            block_seconds=self._policy.login_rate_block_seconds,
        )

        pending_error: ApplicationError | None = None
        result: AuthenticationResultDTO | None = None
        async with self._unit_of_work_factory() as unit_of_work:
            account = await unit_of_work.admin_accounts.get_by_normalized_username(
                normalized_username,
                for_update=True,
            )
            if account is None:
                self._password_hasher.verify_dummy(command.password)
                pending_error = AuthenticationError()
                await unit_of_work.security_events.add(
                    create_security_event(
                        self._id_generator,
                        self._secrets,
                        event_type=SecurityEventType.LOGIN_FAILED,
                        occurred_at=now,
                        client_ip=command.client_ip,
                        user_agent=command.user_agent,
                        details={"reason": "invalid_credentials"},
                    )
                )
            elif account.is_locked(now):
                assert account.locked_until is not None
                pending_error = AccountTemporarilyLockedError(
                    retry_after_seconds=retry_after_seconds(
                        locked_until=account.locked_until,
                        now=now,
                    )
                )
                await self._record_account_failure(
                    unit_of_work,
                    account_id=account.id,
                    command=command,
                    now=now,
                    reason="account_locked",
                )
            elif not account.enabled:
                pending_error = AccountDisabledError()
                await self._record_account_failure(
                    unit_of_work,
                    account_id=account.id,
                    command=command,
                    now=now,
                    reason="account_disabled",
                )
            else:
                verification = self._password_hasher.verify(
                    account.password_hash,
                    command.password,
                )
                if not verification.valid:
                    account.register_failed_login(
                        now=now,
                        maximum_attempts=self._policy.maximum_failed_logins,
                        lock_duration=timedelta(
                            seconds=self._policy.account_lock_seconds
                        ),
                    )
                    await unit_of_work.admin_accounts.save(account)
                    await self._record_account_failure(
                        unit_of_work,
                        account_id=account.id,
                        command=command,
                        now=now,
                        reason="invalid_credentials",
                        failed_attempts=account.failed_login_attempts,
                    )
                    if account.is_locked(now):
                        assert account.locked_until is not None
                        pending_error = AccountTemporarilyLockedError(
                            retry_after_seconds=retry_after_seconds(
                                locked_until=account.locked_until,
                                now=now,
                            )
                        )
                    else:
                        pending_error = AuthenticationError()
                else:
                    if verification.needs_rehash:
                        account.password_hash = self._password_hasher.hash(
                            command.password
                        )
                    account.register_successful_login(now)
                    await unit_of_work.admin_accounts.save(account)
                    result = await self._create_session(
                        unit_of_work=unit_of_work,
                        account_id=account.id,
                        now=now,
                        command=command,
                    )
            await unit_of_work.commit()

        if pending_error is not None:
            raise pending_error
        assert result is not None
        return result

    async def _record_account_failure(
        self,
        unit_of_work: UnitOfWork,
        *,
        account_id: UUID,
        command: LoginCommandDTO,
        now: datetime,
        reason: str,
        failed_attempts: int | None = None,
    ) -> None:
        details: JsonObject = {"reason": reason}
        if failed_attempts is not None:
            details["failed_attempts"] = failed_attempts
        await unit_of_work.security_events.add(
            create_security_event(
                self._id_generator,
                self._secrets,
                event_type=SecurityEventType.LOGIN_FAILED,
                occurred_at=now,
                client_ip=command.client_ip,
                user_agent=command.user_agent,
                admin_id=account_id,
                details=details,
            )
        )

    async def _create_session(
        self,
        *,
        unit_of_work: UnitOfWork,
        account_id: UUID,
        now: datetime,
        command: LoginCommandDTO,
    ) -> AuthenticationResultDTO:
        session_id = self._id_generator.new()
        family_id = self._id_generator.new()
        refresh_jti = self._id_generator.new()
        access_jti = self._id_generator.new()
        expires_at = now + timedelta(seconds=self._policy.refresh_token_ttl_seconds)
        refresh_token = self._jwt_provider.issue_refresh(
            admin_id=account_id,
            session_id=session_id,
            family_id=family_id,
            jti=refresh_jti,
            now=now,
            expires_at=expires_at,
        )
        access_token = self._jwt_provider.issue_access(
            admin_id=account_id,
            session_id=session_id,
            jti=access_jti,
            now=now,
        )
        csrf_token = self._secrets.generate()
        session = AuthSession(
            id=session_id,
            admin_id=account_id,
            family_id=family_id,
            refresh_jti=refresh_jti,
            refresh_token_hash=self._secrets.digest(refresh_token.value),
            csrf_token_hash=self._secrets.digest(csrf_token),
            expires_at=expires_at,
            last_rotated_at=now,
            revoked_at=None,
            revoke_reason=None,
            ip_hash=self._secrets.fingerprint(command.client_ip),
            user_agent_hash=self._secrets.fingerprint(command.user_agent),
            created_at=now,
            updated_at=now,
        )
        await unit_of_work.auth_sessions.add(session)
        await unit_of_work.security_events.add(
            create_security_event(
                self._id_generator,
                self._secrets,
                event_type=SecurityEventType.LOGIN_SUCCEEDED,
                occurred_at=now,
                client_ip=command.client_ip,
                user_agent=command.user_agent,
                admin_id=account_id,
                session_id=session_id,
            )
        )
        return AuthenticationResultDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            session_id=session_id,
        )
