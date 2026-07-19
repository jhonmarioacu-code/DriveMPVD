"""Provision the canonical storage root for existing administrators.

Revision ID: 20260718_0004
Revises: 20260718_0003
Create Date: 2026-07-18
"""

import secrets
import time
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0004"
down_revision: str | None = "20260718_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid7() -> UUID:
    timestamp = time.time_ns() // 1_000_000
    random_value = secrets.randbits(74)
    value = (
        (timestamp << 80)
        | (0x7 << 76)
        | ((random_value >> 62) << 64)
        | (0b10 << 62)
        | (random_value & ((1 << 62) - 1))
    )
    return UUID(int=value)


def upgrade() -> None:
    connection = op.get_bind()
    owner_ids = connection.scalars(sa.text("""
            SELECT admin.id
            FROM admin_accounts AS admin
            WHERE NOT EXISTS (
                SELECT 1
                FROM storage_entries AS root
                WHERE root.owner_id = admin.id
                  AND root.parent_id IS NULL
                  AND root.deleted_at IS NULL
            )
            """)).all()
    for owner_id in owner_ids:
        connection.execute(
            sa.text("""
                INSERT INTO storage_entries (
                    id, owner_id, parent_id, entry_type, name, normalized_name,
                    created_at, updated_at, deleted_at
                ) VALUES (
                    :id, :owner_id, NULL, 'folder', 'Drive', 'drive',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL
                )
                """),
            {"id": _uuid7(), "owner_id": owner_id},
        )


def downgrade() -> None:
    # Roots become user-owned data as soon as files are created. A data-only
    # downgrade must not remove them; revision 0003 already understands rows.
    pass
