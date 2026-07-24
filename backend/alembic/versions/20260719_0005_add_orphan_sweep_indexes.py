"""Index orphan-object reference checks used by the storage outbox worker.

Revision ID: 20260719_0005
Revises: 20260718_0004
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0005"
down_revision: str | None = "20260718_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Support bounded anti-joins without full scans as storage grows."""
    op.create_index(
        "ix_storage_objects_status_created_id",
        "storage_objects",
        ["status", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_thumbnails_storage_object_id",
        "thumbnails",
        ["storage_object_id"],
        unique=False,
        postgresql_where=sa.text("storage_object_id IS NOT NULL"),
    )
    op.create_index(
        "ix_previews_storage_object_id",
        "previews",
        ["storage_object_id"],
        unique=False,
        postgresql_where=sa.text("storage_object_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove only the indexes introduced by this reversible revision."""
    op.drop_index("ix_previews_storage_object_id", table_name="previews")
    op.drop_index("ix_thumbnails_storage_object_id", table_name="thumbnails")
    op.drop_index(
        "ix_storage_objects_status_created_id",
        table_name="storage_objects",
    )
