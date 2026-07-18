"""Create singleton administrator authentication tables.

Revision ID: 20260718_0002
Revises: 20260718_0001
Create Date: 2026-07-18 17:00:00
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0002"
down_revision: str | None = "20260718_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> tuple[sa.Column[Any], ...]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def _uuid7_constraint(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"(get_byte(uuid_send({column}), 6) >> 4) = 7",
        name=op.f(name),
    )


def _add_updated_at_trigger(table_name: str) -> None:
    op.execute(f"""
        CREATE TRIGGER tr_{table_name}_updated_at
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION drivempvd_set_updated_at()
        """)


def upgrade() -> None:
    """Create authentication, session, security audit and rate-limit storage."""
    op.create_table(
        "admin_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "singleton_key",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("normalized_username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "failed_login_attempts >= 0",
            name=op.f("ck_admin_accounts_failed_login_attempts_non_negative"),
        ),
        _uuid7_constraint("id", "ck_admin_accounts_id_uuid_v7"),
        sa.CheckConstraint(
            "singleton_key IS TRUE",
            name=op.f("ck_admin_accounts_singleton_key_true"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_accounts")),
        sa.UniqueConstraint(
            "normalized_username",
            name="uq_admin_accounts_normalized_username",
        ),
        sa.UniqueConstraint(
            "singleton_key",
            name="uq_admin_accounts_singleton_key",
        ),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_jti", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=50), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admin_accounts.id"],
            name=op.f("fk_auth_sessions_admin_id_admin_accounts"),
            ondelete="CASCADE",
        ),
        _uuid7_constraint("family_id", "ck_auth_sessions_family_id_uuid_v7"),
        _uuid7_constraint("id", "ck_auth_sessions_id_uuid_v7"),
        _uuid7_constraint("refresh_jti", "ck_auth_sessions_refresh_jti_uuid_v7"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("refresh_jti", name="uq_auth_sessions_refresh_jti"),
    )
    op.create_index(
        "ix_auth_sessions_admin_active_expiry",
        "auth_sessions",
        ["admin_id", "expires_at"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_auth_sessions_family_id",
        "auth_sessions",
        ["family_id"],
        unique=False,
    )
    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admin_accounts.id"],
            name=op.f("fk_security_events_admin_id_admin_accounts"),
            ondelete="SET NULL",
        ),
        _uuid7_constraint("id", "ck_security_events_id_uuid_v7"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )
    op.create_index(
        "ix_security_events_admin_occurred_id",
        "security_events",
        ["admin_id", "occurred_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_security_events_session_id",
        "security_events",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_security_events_type_occurred_id",
        "security_events",
        ["event_type", "occurred_at", "id"],
        unique=False,
    )
    op.create_table(
        "auth_rate_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        _uuid7_constraint("id", "ck_auth_rate_limits_id_uuid_v7"),
        sa.CheckConstraint(
            "request_count >= 0",
            name=op.f("ck_auth_rate_limits_request_count_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_rate_limits")),
        sa.UniqueConstraint(
            "scope",
            "subject_hash",
            name="uq_auth_rate_limits_scope_subject",
        ),
    )
    op.create_index(
        "ix_auth_rate_limits_blocked_until",
        "auth_rate_limits",
        ["blocked_until"],
        unique=False,
        postgresql_where=sa.text("blocked_until IS NOT NULL"),
    )
    op.create_index(
        "ix_auth_rate_limits_updated_at",
        "auth_rate_limits",
        ["updated_at"],
        unique=False,
    )
    for table_name in (
        "admin_accounts",
        "auth_sessions",
        "security_events",
        "auth_rate_limits",
    ):
        _add_updated_at_trigger(table_name)


def downgrade() -> None:
    """Remove every authentication object created by this revision."""
    for table_name in (
        "auth_rate_limits",
        "security_events",
        "auth_sessions",
        "admin_accounts",
    ):
        op.execute(f"DROP TRIGGER tr_{table_name}_updated_at ON {table_name}")

    op.drop_index("ix_auth_rate_limits_updated_at", table_name="auth_rate_limits")
    op.drop_index("ix_auth_rate_limits_blocked_until", table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_security_events_type_occurred_id", table_name="security_events")
    op.drop_index("ix_security_events_session_id", table_name="security_events")
    op.drop_index("ix_security_events_admin_occurred_id", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_admin_active_expiry", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("admin_accounts")
