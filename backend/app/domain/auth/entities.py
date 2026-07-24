"""Framework-independent authentication aggregates and audit entity."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.domain.auth.enums import SecurityEventType, SessionRevocationReason
from app.shared.json_types import JsonObject


@dataclass(slots=True)
class AdminAccount:
    """The single administrator account aggregate."""

    id: UUID
    username: str
    normalized_username: str
    password_hash: str
    enabled: bool
    failed_login_attempts: int
    locked_until: datetime | None
    password_changed_at: datetime
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def is_locked(self, now: datetime) -> bool:
        """Return whether the temporary credential lock is active."""
        return self.locked_until is not None and self.locked_until > now

    def register_failed_login(
        self,
        *,
        now: datetime,
        maximum_attempts: int,
        lock_duration: timedelta,
    ) -> None:
        """Increase failures and activate a temporary lock at the threshold."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= maximum_attempts:
            self.locked_until = now + lock_duration
        self.updated_at = now

    def register_successful_login(self, now: datetime) -> None:
        """Clear failures and record successful credential use."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = now
        self.updated_at = now

    def change_password(self, *, password_hash: str, now: datetime) -> None:
        """Replace credentials and clear any credential lock state."""
        self.password_hash = password_hash
        self.password_changed_at = now
        self.failed_login_attempts = 0
        self.locked_until = None
        self.updated_at = now


@dataclass(slots=True)
class AuthSession:
    """Refresh-token family and immediate access-token revocation boundary."""

    id: UUID
    admin_id: UUID
    family_id: UUID
    refresh_jti: UUID
    refresh_token_hash: str
    csrf_token_hash: str
    expires_at: datetime
    last_rotated_at: datetime
    revoked_at: datetime | None
    revoke_reason: SessionRevocationReason | None
    ip_hash: str
    user_agent_hash: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        """Return whether this session can authenticate or rotate."""
        return (
            self.revoked_at is None
            and self.deleted_at is None
            and self.expires_at > now
        )

    def rotate(
        self,
        *,
        refresh_jti: UUID,
        refresh_token_hash: str,
        csrf_token_hash: str,
        now: datetime,
    ) -> None:
        """Replace the only valid refresh token for this family."""
        self.refresh_jti = refresh_jti
        self.refresh_token_hash = refresh_token_hash
        self.csrf_token_hash = csrf_token_hash
        self.last_rotated_at = now
        self.updated_at = now

    def revoke(self, *, now: datetime, reason: SessionRevocationReason) -> None:
        """Revoke idempotently while preserving the first reason and instant."""
        if self.revoked_at is None:
            self.revoked_at = now
            self.revoke_reason = reason
            self.updated_at = now


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """Append-only security audit event with privacy-preserving fingerprints."""

    id: UUID
    event_type: SecurityEventType
    occurred_at: datetime
    admin_id: UUID | None
    session_id: UUID | None
    ip_hash: str
    user_agent_hash: str
    details: JsonObject
