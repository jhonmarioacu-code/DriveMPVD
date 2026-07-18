"""Pure helpers shared by authentication use cases."""

import math
import unicodedata
from datetime import datetime
from uuid import UUID

from app.application.exceptions import RateLimitExceededError
from app.application.ports.auth_repositories import RateLimiter
from app.application.ports.auth_services import SecretTokenProvider
from app.application.ports.identifiers import IdGenerator
from app.domain.auth.entities import SecurityEvent
from app.domain.auth.enums import SecurityEventType
from app.shared.json_types import JsonObject


def normalize_username(username: str) -> str:
    """Normalize a login name consistently without locale-sensitive rules."""
    return unicodedata.normalize("NFKC", username).strip().casefold()


def retry_after_seconds(*, locked_until: datetime, now: datetime) -> int:
    """Return an HTTP-compatible positive retry delay."""
    return max(1, math.ceil((locked_until - now).total_seconds()))


async def enforce_rate_limit(
    rate_limiter: RateLimiter,
    *,
    scope: str,
    subject: str,
    now: datetime,
    limit: int,
    window_seconds: int,
    block_seconds: int,
) -> None:
    """Consume one rate unit and raise a typed application error if denied."""
    decision = await rate_limiter.consume(
        scope=scope,
        subject=subject,
        now=now,
        limit=limit,
        window_seconds=window_seconds,
        block_seconds=block_seconds,
    )
    if not decision.allowed:
        raise RateLimitExceededError(retry_after_seconds=decision.retry_after_seconds)


def create_security_event(
    id_generator: IdGenerator,
    secrets: SecretTokenProvider,
    *,
    event_type: SecurityEventType,
    occurred_at: datetime,
    client_ip: str,
    user_agent: str,
    admin_id: UUID | None = None,
    session_id: UUID | None = None,
    details: JsonObject | None = None,
) -> SecurityEvent:
    """Build a privacy-preserving append-only security event."""
    return SecurityEvent(
        id=id_generator.new(),
        event_type=event_type,
        occurred_at=occurred_at,
        admin_id=admin_id,
        session_id=session_id,
        ip_hash=secrets.fingerprint(client_ip),
        user_agent_hash=secrets.fingerprint(user_agent),
        details=details or {},
    )
