"""Refresh-token rotation with reuse detection and CSRF validation."""

from app.application.dtos.auth import (
    AuthenticationResultDTO,
    AuthPolicyDTO,
    RefreshCommandDTO,
)
from app.application.exceptions import (
    AccountDisabledError,
    CsrfValidationError,
    SessionRevokedError,
)
from app.application.ports.auth_repositories import RateLimiter
from app.application.ports.auth_services import (
    Clock,
    JwtProvider,
    SecretTokenProvider,
)
from app.application.ports.identifiers import IdGenerator
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.auth.helpers import (
    create_security_event,
    enforce_rate_limit,
)
from app.domain.auth.enums import SecurityEventType, SessionRevocationReason


class RefreshSessionUseCase:
    """Rotate the single valid refresh token or revoke on detected reuse."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        rate_limiter: RateLimiter,
        jwt_provider: JwtProvider,
        secrets: SecretTokenProvider,
        id_generator: IdGenerator,
        clock: Clock,
        policy: AuthPolicyDTO,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._rate_limiter = rate_limiter
        self._jwt_provider = jwt_provider
        self._secrets = secrets
        self._id_generator = id_generator
        self._clock = clock
        self._policy = policy

    async def execute(self, command: RefreshCommandDTO) -> AuthenticationResultDTO:
        """Validate, rotate atomically and return a new token pair."""
        now = self._clock.now()
        await enforce_rate_limit(
            self._rate_limiter,
            scope="auth.refresh",
            subject=command.client_ip,
            now=now,
            limit=self._policy.refresh_rate_limit,
            window_seconds=self._policy.refresh_rate_window_seconds,
            block_seconds=self._policy.refresh_rate_block_seconds,
        )
        claims = self._jwt_provider.decode_refresh(command.refresh_token, now=now)
        pending_error: SessionRevokedError | None = None
        result: AuthenticationResultDTO | None = None

        async with self._unit_of_work_factory() as unit_of_work:
            session = await unit_of_work.auth_sessions.get(
                claims.session_id,
                for_update=True,
            )
            if session is None or not session.is_active(now):
                raise SessionRevokedError()
            account = await unit_of_work.admin_accounts.get_single(for_update=False)
            if account is None or account.id != claims.admin_id:
                raise SessionRevokedError()
            if not account.enabled:
                raise AccountDisabledError()
            if command.used_cookie:
                self._validate_csrf(command, session.csrf_token_hash)

            valid_current_token = (
                claims.jti == session.refresh_jti
                and claims.family_id == session.family_id
                and self._secrets.matches(
                    command.refresh_token,
                    session.refresh_token_hash,
                )
            )
            if not valid_current_token:
                session.revoke(now=now, reason=SessionRevocationReason.REFRESH_REUSE)
                await unit_of_work.auth_sessions.save(session)
                await unit_of_work.security_events.add(
                    create_security_event(
                        self._id_generator,
                        self._secrets,
                        event_type=SecurityEventType.REFRESH_REUSE_DETECTED,
                        occurred_at=now,
                        client_ip=command.client_ip,
                        user_agent=command.user_agent,
                        admin_id=account.id,
                        session_id=session.id,
                    )
                )
                pending_error = SessionRevokedError()
            else:
                refresh_jti = self._id_generator.new()
                access_jti = self._id_generator.new()
                refresh_token = self._jwt_provider.issue_refresh(
                    admin_id=account.id,
                    session_id=session.id,
                    family_id=session.family_id,
                    jti=refresh_jti,
                    now=now,
                    expires_at=session.expires_at,
                )
                access_token = self._jwt_provider.issue_access(
                    admin_id=account.id,
                    session_id=session.id,
                    jti=access_jti,
                    now=now,
                )
                csrf_token = self._secrets.generate()
                session.rotate(
                    refresh_jti=refresh_jti,
                    refresh_token_hash=self._secrets.digest(refresh_token.value),
                    csrf_token_hash=self._secrets.digest(csrf_token),
                    now=now,
                )
                await unit_of_work.auth_sessions.save(session)
                await unit_of_work.security_events.add(
                    create_security_event(
                        self._id_generator,
                        self._secrets,
                        event_type=SecurityEventType.REFRESH_ROTATED,
                        occurred_at=now,
                        client_ip=command.client_ip,
                        user_agent=command.user_agent,
                        admin_id=account.id,
                        session_id=session.id,
                    )
                )
                result = AuthenticationResultDTO(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    csrf_token=csrf_token,
                    session_id=session.id,
                )
            await unit_of_work.commit()

        if pending_error is not None:
            raise pending_error
        assert result is not None
        return result

    def _validate_csrf(
        self,
        command: RefreshCommandDTO,
        expected_digest: str,
    ) -> None:
        if (
            command.csrf_cookie is None
            or command.csrf_header is None
            or not self._secrets.matches(command.csrf_cookie, expected_digest)
            or not self._secrets.matches(command.csrf_header, expected_digest)
        ):
            raise CsrfValidationError()
