"""SQLAlchemy authentication repositories with explicit domain mapping."""

import math
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dtos.auth import RateLimitDecisionDTO
from app.application.ports.auth_services import SecretTokenProvider
from app.application.ports.identifiers import IdGenerator
from app.domain.auth.entities import AdminAccount, AuthSession, SecurityEvent
from app.domain.auth.enums import SessionRevocationReason
from app.infrastructure.exceptions import PersistenceError
from app.infrastructure.persistence.models.auth import (
    AdminAccountModel,
    AuthRateLimitModel,
    AuthSessionModel,
    SecurityEventModel,
)


class SQLAlchemyAdminAccountRepository:
    """Map the singleton account aggregate without exposing ORM state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_single(self, *, for_update: bool = False) -> AdminAccount | None:
        statement = select(AdminAccountModel).where(
            AdminAccountModel.deleted_at.is_(None)
        )
        if for_update:
            statement = statement.with_for_update()
        try:
            model = await self._session.scalar(statement)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if model is None else self._to_domain(model)

    async def get_by_normalized_username(
        self,
        normalized_username: str,
        *,
        for_update: bool = False,
    ) -> AdminAccount | None:
        statement = select(AdminAccountModel).where(
            AdminAccountModel.normalized_username == normalized_username,
            AdminAccountModel.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        try:
            model = await self._session.scalar(statement)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if model is None else self._to_domain(model)

    async def add(self, account: AdminAccount) -> None:
        self._session.add(
            AdminAccountModel(
                id=account.id,
                singleton_key=True,
                username=account.username,
                normalized_username=account.normalized_username,
                password_hash=account.password_hash,
                enabled=account.enabled,
                failed_login_attempts=account.failed_login_attempts,
                locked_until=account.locked_until,
                password_changed_at=account.password_changed_at,
                last_login_at=account.last_login_at,
                created_at=account.created_at,
                updated_at=account.updated_at,
                deleted_at=account.deleted_at,
            )
        )
        await self._flush()

    async def save(self, account: AdminAccount) -> None:
        statement = (
            update(AdminAccountModel)
            .where(AdminAccountModel.id == account.id)
            .values(
                username=account.username,
                normalized_username=account.normalized_username,
                password_hash=account.password_hash,
                enabled=account.enabled,
                failed_login_attempts=account.failed_login_attempts,
                locked_until=account.locked_until,
                password_changed_at=account.password_changed_at,
                last_login_at=account.last_login_at,
                updated_at=account.updated_at,
                deleted_at=account.deleted_at,
            )
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        if result.rowcount != 1:
            raise PersistenceError("The administrator account no longer exists.")

    async def _flush(self) -> None:
        try:
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    @staticmethod
    def _to_domain(model: AdminAccountModel) -> AdminAccount:
        return AdminAccount(
            id=model.id,
            username=model.username,
            normalized_username=model.normalized_username,
            password_hash=model.password_hash,
            enabled=model.enabled,
            failed_login_attempts=model.failed_login_attempts,
            locked_until=model.locked_until,
            password_changed_at=model.password_changed_at,
            last_login_at=model.last_login_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )


class SQLAlchemyAuthSessionRepository:
    """Persist refresh families and immediate revocation state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> AuthSession | None:
        statement = select(AuthSessionModel).where(
            AuthSessionModel.id == session_id,
            AuthSessionModel.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        try:
            model = await self._session.scalar(statement)
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return None if model is None else self._to_domain(model)

    async def add(self, session: AuthSession) -> None:
        self._session.add(self._to_model(session))
        try:
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    async def save(self, session: AuthSession) -> None:
        statement = (
            update(AuthSessionModel)
            .where(AuthSessionModel.id == session.id)
            .values(
                refresh_jti=session.refresh_jti,
                refresh_token_hash=session.refresh_token_hash,
                csrf_token_hash=session.csrf_token_hash,
                expires_at=session.expires_at,
                last_rotated_at=session.last_rotated_at,
                revoked_at=session.revoked_at,
                revoke_reason=(
                    session.revoke_reason.value
                    if session.revoke_reason is not None
                    else None
                ),
                ip_hash=session.ip_hash,
                user_agent_hash=session.user_agent_hash,
                updated_at=session.updated_at,
                deleted_at=session.deleted_at,
            )
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        if result.rowcount != 1:
            raise PersistenceError("The authentication session no longer exists.")

    async def revoke_all_active(
        self,
        *,
        admin_id: UUID,
        now: datetime,
        reason: SessionRevocationReason,
    ) -> int:
        statement = (
            update(AuthSessionModel)
            .where(
                AuthSessionModel.admin_id == admin_id,
                AuthSessionModel.revoked_at.is_(None),
                AuthSessionModel.deleted_at.is_(None),
            )
            .values(revoked_at=now, revoke_reason=reason.value, updated_at=now)
        )
        try:
            result = cast(CursorResult[Any], await self._session.execute(statement))
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc
        return result.rowcount

    @staticmethod
    def _to_model(session: AuthSession) -> AuthSessionModel:
        return AuthSessionModel(
            id=session.id,
            admin_id=session.admin_id,
            family_id=session.family_id,
            refresh_jti=session.refresh_jti,
            refresh_token_hash=session.refresh_token_hash,
            csrf_token_hash=session.csrf_token_hash,
            expires_at=session.expires_at,
            last_rotated_at=session.last_rotated_at,
            revoked_at=session.revoked_at,
            revoke_reason=(
                session.revoke_reason.value
                if session.revoke_reason is not None
                else None
            ),
            ip_hash=session.ip_hash,
            user_agent_hash=session.user_agent_hash,
            created_at=session.created_at,
            updated_at=session.updated_at,
            deleted_at=session.deleted_at,
        )

    @staticmethod
    def _to_domain(model: AuthSessionModel) -> AuthSession:
        return AuthSession(
            id=model.id,
            admin_id=model.admin_id,
            family_id=model.family_id,
            refresh_jti=model.refresh_jti,
            refresh_token_hash=model.refresh_token_hash,
            csrf_token_hash=model.csrf_token_hash,
            expires_at=model.expires_at,
            last_rotated_at=model.last_rotated_at,
            revoked_at=model.revoked_at,
            revoke_reason=(
                SessionRevocationReason(model.revoke_reason)
                if model.revoke_reason is not None
                else None
            ),
            ip_hash=model.ip_hash,
            user_agent_hash=model.user_agent_hash,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )


class SQLAlchemySecurityEventRepository:
    """Append security events without adding navigable ORM relationships."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: SecurityEvent) -> None:
        self._session.add(
            SecurityEventModel(
                id=event.id,
                event_type=event.event_type.value,
                occurred_at=event.occurred_at,
                admin_id=event.admin_id,
                session_id=event.session_id,
                ip_hash=event.ip_hash,
                user_agent_hash=event.user_agent_hash,
                details=dict(event.details),
            )
        )
        try:
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc


class PostgreSQLRateLimiter:
    """Serialize one subject bucket using a transaction-scoped advisory lock."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        id_generator: IdGenerator,
        secrets: SecretTokenProvider,
    ) -> None:
        self._session_factory = session_factory
        self._id_generator = id_generator
        self._secrets = secrets

    async def consume(
        self,
        *,
        scope: str,
        subject: str,
        now: datetime,
        limit: int,
        window_seconds: int,
        block_seconds: int,
    ) -> RateLimitDecisionDTO:
        subject_hash = self._secrets.fingerprint(subject)
        lock_key = f"{scope}:{subject_hash}"
        try:
            async with self._session_factory.begin() as session:
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": lock_key},
                )
                model = await session.scalar(
                    select(AuthRateLimitModel)
                    .where(
                        AuthRateLimitModel.scope == scope,
                        AuthRateLimitModel.subject_hash == subject_hash,
                    )
                    .with_for_update()
                )
                return await self._consume_locked(
                    session,
                    model=model,
                    scope=scope,
                    subject_hash=subject_hash,
                    now=now,
                    limit=limit,
                    window_seconds=window_seconds,
                    block_seconds=block_seconds,
                )
        except SQLAlchemyError as exc:
            raise PersistenceError() from exc

    async def _consume_locked(
        self,
        session: AsyncSession,
        *,
        model: AuthRateLimitModel | None,
        scope: str,
        subject_hash: str,
        now: datetime,
        limit: int,
        window_seconds: int,
        block_seconds: int,
    ) -> RateLimitDecisionDTO:
        if model is None:
            session.add(
                AuthRateLimitModel(
                    id=self._id_generator.new(),
                    scope=scope,
                    subject_hash=subject_hash,
                    window_started_at=now,
                    request_count=1,
                    blocked_until=None,
                )
            )
            await session.flush()
            return RateLimitDecisionDTO(allowed=True, retry_after_seconds=0)

        if model.blocked_until is not None and model.blocked_until > now:
            return RateLimitDecisionDTO(
                allowed=False,
                retry_after_seconds=max(
                    1,
                    math.ceil((model.blocked_until - now).total_seconds()),
                ),
            )

        window_ends = model.window_started_at + timedelta(seconds=window_seconds)
        if window_ends <= now:
            model.window_started_at = now
            model.request_count = 1
            model.blocked_until = None
            model.updated_at = now
            return RateLimitDecisionDTO(allowed=True, retry_after_seconds=0)

        model.request_count += 1
        model.updated_at = now
        if model.request_count > limit:
            model.blocked_until = now + timedelta(seconds=block_seconds)
            return RateLimitDecisionDTO(
                allowed=False,
                retry_after_seconds=block_seconds,
            )
        return RateLimitDecisionDTO(allowed=True, retry_after_seconds=0)
