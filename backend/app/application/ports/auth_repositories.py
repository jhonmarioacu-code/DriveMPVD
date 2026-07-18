"""Authentication repository ports implemented by persistence adapters."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dtos.auth import RateLimitDecisionDTO
from app.domain.auth.entities import AdminAccount, AuthSession, SecurityEvent
from app.domain.auth.enums import SessionRevocationReason


class AdminAccountRepository(Protocol):
    """Repository for the singleton administrator aggregate."""

    async def get_single(self, *, for_update: bool = False) -> AdminAccount | None: ...

    async def get_by_normalized_username(
        self,
        normalized_username: str,
        *,
        for_update: bool = False,
    ) -> AdminAccount | None: ...

    async def add(self, account: AdminAccount) -> None: ...

    async def save(self, account: AdminAccount) -> None: ...


class AuthSessionRepository(Protocol):
    """Repository for refresh-token session aggregates."""

    async def get(
        self, session_id: UUID, *, for_update: bool = False
    ) -> AuthSession | None: ...

    async def add(self, session: AuthSession) -> None: ...

    async def save(self, session: AuthSession) -> None: ...

    async def revoke_all_active(
        self,
        *,
        admin_id: UUID,
        now: datetime,
        reason: SessionRevocationReason,
    ) -> int: ...


class SecurityEventRepository(Protocol):
    """Append-only security audit repository."""

    async def add(self, event: SecurityEvent) -> None: ...


class RateLimiter(Protocol):
    """Atomic rate limiter with its own short database transaction."""

    async def consume(
        self,
        *,
        scope: str,
        subject: str,
        now: datetime,
        limit: int,
        window_seconds: int,
        block_seconds: int,
    ) -> RateLimitDecisionDTO: ...
