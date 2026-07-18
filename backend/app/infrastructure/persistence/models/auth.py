"""ORM mappings for the singleton administrator and authentication audit."""

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import AuditColumnsMixin, Base


class AdminAccountModel(AuditColumnsMixin, Base):
    """Persistence-only mapping enforcing at most one administrator."""

    __tablename__ = "admin_accounts"
    __table_args__ = (
        CheckConstraint("singleton_key IS TRUE", name="singleton_key_true"),
        CheckConstraint(
            "(get_byte(uuid_send(id), 6) >> 4) = 7",
            name="id_uuid_v7",
        ),
        CheckConstraint(
            "failed_login_attempts >= 0",
            name="failed_login_attempts_non_negative",
        ),
        UniqueConstraint("singleton_key", name="uq_admin_accounts_singleton_key"),
        UniqueConstraint(
            "normalized_username",
            name="uq_admin_accounts_normalized_username",
        ),
    )
    __mapper_args__: ClassVar[dict[str, bool]] = {  # type: ignore[misc]
        "eager_defaults": True
    }

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    singleton_key: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSessionModel(AuditColumnsMixin, Base):
    """One rotating refresh-token family and revocation state."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint(
            "(get_byte(uuid_send(id), 6) >> 4) = 7",
            name="id_uuid_v7",
        ),
        CheckConstraint(
            "(get_byte(uuid_send(family_id), 6) >> 4) = 7",
            name="family_id_uuid_v7",
        ),
        CheckConstraint(
            "(get_byte(uuid_send(refresh_jti), 6) >> 4) = 7",
            name="refresh_jti_uuid_v7",
        ),
        UniqueConstraint("refresh_jti", name="uq_auth_sessions_refresh_jti"),
        Index(
            "ix_auth_sessions_admin_active_expiry",
            "admin_id",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL AND deleted_at IS NULL"),
        ),
        Index("ix_auth_sessions_family_id", "family_id"),
    )
    __mapper_args__: ClassVar[dict[str, bool]] = {  # type: ignore[misc]
        "eager_defaults": True
    }

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    admin_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    refresh_jti: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_rotated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(50))
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class SecurityEventModel(AuditColumnsMixin, Base):
    """Append-only security event; relationships are intentionally absent."""

    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint(
            "(get_byte(uuid_send(id), 6) >> 4) = 7",
            name="id_uuid_v7",
        ),
        Index("ix_security_events_type_occurred_id", "event_type", "occurred_at", "id"),
        Index(
            "ix_security_events_admin_occurred_id",
            "admin_id",
            "occurred_at",
            "id",
        ),
        Index("ix_security_events_session_id", "session_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    admin_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
    )
    session_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class AuthRateLimitModel(AuditColumnsMixin, Base):
    """Database-coordinated rate limit bucket."""

    __tablename__ = "auth_rate_limits"
    __table_args__ = (
        CheckConstraint(
            "(get_byte(uuid_send(id), 6) >> 4) = 7",
            name="id_uuid_v7",
        ),
        CheckConstraint("request_count >= 0", name="request_count_non_negative"),
        UniqueConstraint(
            "scope",
            "subject_hash",
            name="uq_auth_rate_limits_scope_subject",
        ),
        Index(
            "ix_auth_rate_limits_blocked_until",
            "blocked_until",
            postgresql_where=text("blocked_until IS NOT NULL"),
        ),
        Index("ix_auth_rate_limits_updated_at", "updated_at"),
    )
    __mapper_args__: ClassVar[dict[str, bool]] = {  # type: ignore[misc]
        "eager_defaults": True
    }

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
