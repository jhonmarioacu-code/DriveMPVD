"""Create per-account favorites and recent-open projections.

Revision ID: 20260720_0006
Revises: 20260719_0005
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0006"
down_revision: str | None = "20260719_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store idempotent favorites and bounded recent-entry history."""
    op.create_table(
        "favorites",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["admin_accounts.id"],
            name=op.f("fk_favorites_owner_id_admin_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["storage_entries.id"],
            name=op.f("fk_favorites_entry_id_storage_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("owner_id", "entry_id", name=op.f("pk_favorites")),
    )
    op.create_index(
        "ix_favorites_owner_created_entry",
        "favorites",
        ["owner_id", "created_at", "entry_id"],
        unique=False,
    )
    op.create_index("ix_favorites_entry_id", "favorites", ["entry_id"], unique=False)

    op.create_table(
        "recent_opens",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "open_count >= 1",
            name=op.f("ck_recent_opens_open_count_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["admin_accounts.id"],
            name=op.f("fk_recent_opens_owner_id_admin_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["storage_entries.id"],
            name=op.f("fk_recent_opens_entry_id_storage_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "owner_id",
            "entry_id",
            name=op.f("pk_recent_opens"),
        ),
    )
    op.create_index(
        "ix_recent_opens_owner_opened_entry",
        "recent_opens",
        ["owner_id", "opened_at", "entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_recent_opens_entry_id",
        "recent_opens",
        ["entry_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove activity projections without changing storage metadata."""
    op.drop_index("ix_recent_opens_entry_id", table_name="recent_opens")
    op.drop_index(
        "ix_recent_opens_owner_opened_entry",
        table_name="recent_opens",
    )
    op.drop_table("recent_opens")
    op.drop_index("ix_favorites_entry_id", table_name="favorites")
    op.drop_index("ix_favorites_owner_created_entry", table_name="favorites")
    op.drop_table("favorites")
