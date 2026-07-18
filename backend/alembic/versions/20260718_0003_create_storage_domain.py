"""Create logical storage domain persistence.

Revision ID: 20260718_0003
Revises: 20260718_0002
Create Date: 2026-07-18 18:00:00
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0003"
down_revision: str | None = "20260718_0002"
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


def _uuid7_constraint(table_name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "(get_byte(uuid_send(id), 6) >> 4) = 7",
        name=op.f(f"ck_{table_name}_id_uuid_v7"),
    )


def _add_updated_at_trigger(table_name: str) -> None:
    op.execute(f"""
        CREATE TRIGGER tr_{table_name}_updated_at
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION drivempvd_set_updated_at()
        """)


def upgrade() -> None:
    """Create storage tree, immutable objects, versions and future job records."""
    op.create_table(
        "storage_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        *_audit_columns(),
        _uuid7_constraint("storage_entries"),
        sa.CheckConstraint(
            "entry_type IN ('folder', 'file')",
            name=op.f("ck_storage_entries_entry_type_valid"),
        ),
        sa.CheckConstraint(
            "parent_id IS NOT NULL OR entry_type = 'folder'",
            name=op.f("ck_storage_entries_root_must_be_folder"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["admin_accounts.id"],
            name=op.f("fk_storage_entries_owner_id_admin_accounts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["storage_entries.id"],
            name=op.f("fk_storage_entries_parent_id_storage_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_entries")),
    )
    op.create_index(
        "uq_storage_entries_active_sibling_name",
        "storage_entries",
        ["parent_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_storage_entries_owner_root",
        "storage_entries",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_storage_entries_parent_active_name_id",
        "storage_entries",
        ["parent_id", "normalized_name", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_storage_entries_owner_updated_id",
        "storage_entries",
        ["owner_id", "updated_at", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_storage_entries_deleted_at",
        "storage_entries",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    op.create_table(
        "storage_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_audit_columns(),
        _uuid7_constraint("storage_objects"),
        sa.CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_storage_objects_checksum_sha256_valid"),
        ),
        sa.CheckConstraint(
            "size >= 0",
            name=op.f("ck_storage_objects_size_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_objects")),
        sa.UniqueConstraint(
            "storage_key",
            name="uq_storage_objects_storage_key",
        ),
    )
    op.create_index(
        "ix_storage_objects_checksum_size",
        "storage_objects",
        ["checksum_sha256", "size"],
        unique=False,
    )
    op.create_index(
        "ix_storage_objects_status_updated",
        "storage_objects",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "file_metadata",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("internal_name", sa.String(length=300), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=50), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("current_version_number", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_file_metadata_checksum_sha256_valid"),
        ),
        sa.CheckConstraint(
            "current_version_number >= 1",
            name=op.f("ck_file_metadata_current_version_positive"),
        ),
        sa.CheckConstraint(
            "size >= 0",
            name=op.f("ck_file_metadata_size_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["storage_entries.id"],
            name=op.f("fk_file_metadata_entry_id_storage_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entry_id", name=op.f("pk_file_metadata")),
        sa.UniqueConstraint(
            "internal_name",
            name="uq_file_metadata_internal_name",
        ),
    )
    for index_name, columns in (
        ("ix_file_metadata_checksum_size", ["checksum_sha256", "size"]),
        ("ix_file_metadata_extension", ["extension"]),
        ("ix_file_metadata_mime_type", ["mime_type"]),
        ("ix_file_metadata_size", ["size"]),
    ):
        op.create_index(index_name, "file_metadata", columns, unique=False)

    op.create_table(
        "file_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=50), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        _uuid7_constraint("file_versions"),
        sa.CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_file_versions_checksum_sha256_valid"),
        ),
        sa.CheckConstraint(
            "size >= 0",
            name=op.f("ck_file_versions_size_non_negative"),
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name=op.f("ck_file_versions_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["admin_accounts.id"],
            name=op.f("fk_file_versions_created_by_admin_accounts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["file_metadata.entry_id"],
            name=op.f("fk_file_versions_file_id_file_metadata"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_object_id"],
            ["storage_objects.id"],
            name=op.f("fk_file_versions_storage_object_id_storage_objects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_versions")),
        sa.UniqueConstraint(
            "file_id",
            "version_number",
            name="uq_file_versions_file_version",
        ),
    )
    op.create_index(
        "ix_file_versions_storage_object_id",
        "file_versions",
        ["storage_object_id"],
        unique=False,
    )

    _create_derived_asset_tables()
    _create_upload_and_trash_tables()

    for table_name in (
        "storage_entries",
        "storage_objects",
        "thumbnails",
        "previews",
        "upload_sessions",
    ):
        _add_updated_at_trigger(table_name)


def _create_derived_asset_tables() -> None:
    op.create_table(
        "thumbnails",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variant", sa.String(length=50), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_audit_columns(),
        _uuid7_constraint("thumbnails"),
        sa.CheckConstraint(
            "height IS NULL OR height > 0",
            name=op.f("ck_thumbnails_height_positive"),
        ),
        sa.CheckConstraint(
            "width IS NULL OR width > 0",
            name=op.f("ck_thumbnails_width_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["file_version_id"],
            ["file_versions.id"],
            name=op.f("fk_thumbnails_file_version_id_file_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_object_id"],
            ["storage_objects.id"],
            name=op.f("fk_thumbnails_storage_object_id_storage_objects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_thumbnails")),
        sa.UniqueConstraint(
            "file_version_id",
            "variant",
            name="uq_thumbnails_version_variant",
        ),
    )
    op.create_table(
        "previews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variant", sa.String(length=50), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_audit_columns(),
        _uuid7_constraint("previews"),
        sa.ForeignKeyConstraint(
            ["file_version_id"],
            ["file_versions.id"],
            name=op.f("fk_previews_file_version_id_file_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_object_id"],
            ["storage_objects.id"],
            name=op.f("fk_previews_storage_object_id_storage_objects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_previews")),
        sa.UniqueConstraint(
            "file_version_id",
            "variant",
            name="uq_previews_version_variant",
        ),
    )


def _create_upload_and_trash_tables() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("internal_name", sa.String(length=300), nullable=False),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("extension", sa.String(length=50), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("staging_key", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_columns(),
        _uuid7_constraint("upload_sessions"),
        sa.CheckConstraint(
            "checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_upload_sessions_checksum_sha256_valid"),
        ),
        sa.CheckConstraint(
            "expected_size >= 0",
            name=op.f("ck_upload_sessions_expected_size_non_negative"),
        ),
        sa.CheckConstraint(
            "uploaded_bytes >= 0 AND uploaded_bytes <= expected_size",
            name=op.f("ck_upload_sessions_uploaded_bytes_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["admin_accounts.id"],
            name=op.f("fk_upload_sessions_owner_id_admin_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["storage_entries.id"],
            name=op.f("fk_upload_sessions_parent_id_storage_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upload_sessions")),
        sa.UniqueConstraint(
            "staging_key",
            name="uq_upload_sessions_staging_key",
        ),
    )
    op.create_index(
        "ix_upload_sessions_owner_status",
        "upload_sessions",
        ["owner_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_upload_sessions_expires_at",
        "upload_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "trash_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_parent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=False),
        _uuid7_constraint("trash_items"),
        sa.ForeignKeyConstraint(
            ["deleted_by"],
            ["admin_accounts.id"],
            name=op.f("fk_trash_items_deleted_by_admin_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["storage_entries.id"],
            name=op.f("fk_trash_items_entry_id_storage_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trash_items")),
        sa.UniqueConstraint("entry_id", name="uq_trash_items_entry_id"),
    )
    op.create_index(
        "ix_trash_items_deleted_by_trashed",
        "trash_items",
        ["deleted_by", "trashed_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove every storage domain object created by this revision."""
    for table_name in (
        "upload_sessions",
        "previews",
        "thumbnails",
        "storage_objects",
        "storage_entries",
    ):
        op.execute(f"DROP TRIGGER tr_{table_name}_updated_at ON {table_name}")

    op.drop_index("ix_trash_items_deleted_by_trashed", table_name="trash_items")
    op.drop_table("trash_items")
    op.drop_index("ix_upload_sessions_expires_at", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_owner_status", table_name="upload_sessions")
    op.drop_table("upload_sessions")
    op.drop_table("previews")
    op.drop_table("thumbnails")
    op.drop_index("ix_file_versions_storage_object_id", table_name="file_versions")
    op.drop_table("file_versions")
    for index_name in (
        "ix_file_metadata_size",
        "ix_file_metadata_mime_type",
        "ix_file_metadata_extension",
        "ix_file_metadata_checksum_size",
    ):
        op.drop_index(index_name, table_name="file_metadata")
    op.drop_table("file_metadata")
    op.drop_index("ix_storage_objects_status_updated", table_name="storage_objects")
    op.drop_index("ix_storage_objects_checksum_size", table_name="storage_objects")
    op.drop_table("storage_objects")
    for index_name in (
        "ix_storage_entries_deleted_at",
        "ix_storage_entries_owner_updated_id",
        "ix_storage_entries_parent_active_name_id",
        "uq_storage_entries_owner_root",
        "uq_storage_entries_active_sibling_name",
    ):
        op.drop_index(index_name, table_name="storage_entries")
    op.drop_table("storage_entries")
