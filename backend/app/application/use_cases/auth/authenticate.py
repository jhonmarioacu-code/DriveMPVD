"""Access-token authentication and cookie CSRF verification."""

from app.application.dtos.auth import AdminPrincipalDTO
from app.application.exceptions import (
    AccountDisabledError,
    CsrfValidationError,
    SessionRevokedError,
)
from app.application.ports.auth_services import Clock, JwtProvider, SecretTokenProvider
from app.application.ports.unit_of_work import UnitOfWorkFactory


class AuthenticateAccessUseCase:
    """Resolve an access JWT to the one enabled administrator."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        jwt_provider: JwtProvider,
        secrets: SecretTokenProvider,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._jwt_provider = jwt_provider
        self._secrets = secrets
        self._clock = clock

    async def execute(
        self,
        token: str,
        *,
        authenticated_via_cookie: bool,
        require_csrf: bool = False,
        csrf_cookie: str | None = None,
        csrf_header: str | None = None,
    ) -> AdminPrincipalDTO:
        """Validate claims, revocation, singleton identity and optional CSRF."""
        now = self._clock.now()
        claims = self._jwt_provider.decode_access(token, now=now)
        async with self._unit_of_work_factory() as unit_of_work:
            session = await unit_of_work.auth_sessions.get(claims.session_id)
            if session is None or not session.is_active(now):
                raise SessionRevokedError()
            account = await unit_of_work.admin_accounts.get_single()
            if account is None or account.id != claims.admin_id:
                raise SessionRevokedError()
            if not account.enabled:
                raise AccountDisabledError()
            if (
                authenticated_via_cookie
                and require_csrf
                and (
                    csrf_cookie is None
                    or csrf_header is None
                    or not self._secrets.matches(
                        csrf_cookie,
                        session.csrf_token_hash,
                    )
                    or not self._secrets.matches(
                        csrf_header,
                        session.csrf_token_hash,
                    )
                )
            ):
                raise CsrfValidationError()
            return AdminPrincipalDTO(
                admin_id=account.id,
                session_id=session.id,
                username=account.username,
                authenticated_via_cookie=authenticated_via_cookie,
            )
