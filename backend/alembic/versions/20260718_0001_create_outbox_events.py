"""Create audited transactional outbox.

Revision ID: 20260718_0001
Revises: None
Create Date: 2026-07-18 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the outbox table, audit trigger and query indexes."""
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "attempts >= 0",
            name=op.f("ck_outbox_events_attempts_non_negative"),
        ),
        sa.CheckConstraint(
            "(get_byte(uuid_send(id), 6) >> 4) = 7",
            name=op.f("ck_outbox_events_id_uuid_v7"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.execute("""
        CREATE FUNCTION drivempvd_set_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$
        """)
    op.execute("""
        CREATE TRIGGER tr_outbox_events_updated_at
        BEFORE UPDATE ON outbox_events
        FOR EACH ROW
        EXECUTE FUNCTION drivempvd_set_updated_at()
        """)
    op.create_index(
        "ix_outbox_events_pending_created_id",
        "outbox_events",
        ["created_at", "id"],
        unique=False,
        postgresql_where=sa.text("processed_at IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_outbox_events_aggregate_created_id",
        "outbox_events",
        ["aggregate_id", "created_at", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_outbox_events_type_created_id",
        "outbox_events",
        ["event_type", "created_at", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_outbox_events_deleted_at",
        "outbox_events",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove every object introduced by this revision."""
    op.drop_index("ix_outbox_events_deleted_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_type_created_id", table_name="outbox_events")
    op.drop_index(
        "ix_outbox_events_aggregate_created_id",
        table_name="outbox_events",
    )
    op.drop_index("ix_outbox_events_pending_created_id", table_name="outbox_events")
    op.execute("DROP TRIGGER tr_outbox_events_updated_at ON outbox_events")
    op.drop_table("outbox_events")
    op.execute("DROP FUNCTION drivempvd_set_updated_at()")
