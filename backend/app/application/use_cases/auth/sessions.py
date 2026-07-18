"""Session logout and administrator-wide revocation use cases."""

from app.application.dtos.auth import AdminPrincipalDTO
from app.application.ports.auth_services import Clock, SecretTokenProvider
from app.application.ports.identifiers import IdGenerator
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.auth.helpers import create_security_event
from app.domain.auth.enums import SecurityEventType, SessionRevocationReason


class LogoutUseCase:
    """Revoke the principal's current session idempotently."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        id_generator: IdGenerator,
        secrets: SecretTokenProvider,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._id_generator = id_generator
        self._secrets = secrets
        self._clock = clock

    async def execute(
        self,
        principal: AdminPrincipalDTO,
        *,
        client_ip: str,
        user_agent: str,
    ) -> None:
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            session = await unit_of_work.auth_sessions.get(
                principal.session_id,
                for_update=True,
            )
            if session is not None:
                session.revoke(now=now, reason=SessionRevocationReason.LOGOUT)
                await unit_of_work.auth_sessions.save(session)
            await unit_of_work.security_events.add(
                create_security_event(
                    self._id_generator,
                    self._secrets,
                    event_type=SecurityEventType.LOGOUT,
                    occurred_at=now,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    admin_id=principal.admin_id,
                    session_id=principal.session_id,
                )
            )
            await unit_of_work.commit()


class RevokeAllSessionsUseCase:
    """Revoke every active session for the singleton administrator."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        id_generator: IdGenerator,
        secrets: SecretTokenProvider,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._id_generator = id_generator
        self._secrets = secrets
        self._clock = clock

    async def execute(
        self,
        principal: AdminPrincipalDTO,
        *,
        client_ip: str,
        user_agent: str,
    ) -> int:
        now = self._clock.now()
        async with self._unit_of_work_factory() as unit_of_work:
            count = await unit_of_work.auth_sessions.revoke_all_active(
                admin_id=principal.admin_id,
                now=now,
                reason=SessionRevocationReason.ADMIN_ACTION,
            )
            await unit_of_work.security_events.add(
                create_security_event(
                    self._id_generator,
                    self._secrets,
                    event_type=SecurityEventType.ALL_SESSIONS_REVOKED,
                    occurred_at=now,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    admin_id=principal.admin_id,
                    session_id=principal.session_id,
                    details={"revoked_sessions": count},
                )
            )
            await unit_of_work.commit()
        return count
