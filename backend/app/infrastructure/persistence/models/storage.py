"""ORM mappings for the logical storage bounded context."""

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import AuditColumnsMixin, Base


def _uuid7_check(column: str, name: str) -> CheckConstraint:
    return CheckConstraint(
        f"(get_byte(uuid_send({column}), 6) >> 4) = 7",
        name=name,
    )


class StorageEntryModel(AuditColumnsMixin, Base):
    __tablename__ = "storage_entries"
    __table_args__ = (
        _uuid7_check("id", "id_uuid_v7"),
        CheckConstraint(
            "parent_id IS NOT NULL OR entry_type = 'folder'",
            name="root_must_be_folder",
        ),
        CheckConstraint(
            "entry_type IN ('folder', 'file')",
            name="entry_type_valid",
        ),
        Index(
            "uq_storage_entries_active_sibling_name",
            "parent_id",
            "normalized_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_storage_entries_owner_root",
            "owner_id",
            unique=True,
            postgresql_where=text("parent_id IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "ix_storage_entries_parent_active_name_id",
            "parent_id",
            "normalized_name",
            "id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_storage_entries_owner_updated_id",
            "owner_id",
            "updated_at",
            "id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_storage_entries_deleted_at",
            "deleted_at",
            postgresql_where=text("deleted_at IS NOT NULL"),
        ),
    )
    __mapper_args__: ClassVar[dict[str, bool]] = {  # type: ignore[misc]
        "eager_defaults": True
    }

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_entries.id", ondelete="CASCADE"),
    )
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)


class FileMetadataModel(Base):
    __tablename__ = "file_metadata"
    __table_args__ = (
        CheckConstraint("size >= 0", name="size_non_negative"),
        CheckConstraint(
            "current_version_number >= 1",
            name="current_version_positive",
        ),
        CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_sha256_valid",
        ),
        UniqueConstraint("internal_name", name="uq_file_metadata_internal_name"),
        Index("ix_file_metadata_checksum_size", "checksum_sha256", "size"),
        Index("ix_file_metadata_mime_type", "mime_type"),
        Index("ix_file_metadata_extension", "extension"),
        Index("ix_file_metadata_size", "size"),
    )

    entry_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_name: Mapped[str] = mapped_column(String(300), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(50), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False)


class StorageObjectModel(AuditColumnsMixin, Base):
    __tablename__ = "storage_objects"
    __table_args__ = (
        _uuid7_check("id", "id_uuid_v7"),
        CheckConstraint("size >= 0", name="size_non_negative"),
        CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_sha256_valid",
        ),
        UniqueConstraint("storage_key", name="uq_storage_objects_storage_key"),
        Index("ix_storage_objects_checksum_size", "checksum_sha256", "size"),
        Index("ix_storage_objects_status_updated", "status", "updated_at"),
    )
    __mapper_args__: ClassVar[dict[str, bool]] = {  # type: ignore[misc]
        "eager_defaults": True
    }

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class FileVersionModel(Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        _uuid7_check("id", "id_uuid_v7"),
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("size >= 0", name="size_non_negative"),
        CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_sha256_valid",
        ),
        UniqueConstraint(
            "file_id",
            "version_number",
            name="uq_file_versions_file_version",
        ),
        Index("ix_file_versions_storage_object_id", "storage_object_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    file_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("file_metadata.entry_id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_object_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_objects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(50), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class ThumbnailModel(AuditColumnsMixin, Base):
    __tablename__ = "thumbnails"
    __table_args__ = (
        _uuid7_check("id", "id_uuid_v7"),
        UniqueConstraint(
            "file_version_id",
            "variant",
            name="uq_thumbnails_version_variant",
        ),
        CheckConstraint("width IS NULL OR width > 0", name="width_positive"),
        CheckConstraint("height IS NULL OR height > 0", name="height_positive"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    file_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_object_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_objects.id", ondelete="SET NULL"),
    )
    variant: Mapped[str] = mapped_column(String(50), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class PreviewModel(AuditColumnsMixin, Base):
    __tablename__ = "previews"
    __table_args__ = (
        _uuid7_check("id", "id_uuid_v7"),
        UniqueConstraint(
            "file_version_id",
            "variant",
            name="uq_previews_version_variant",
        ),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    file_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_object_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_objects.id", ondelete="SET NULL"),
    )
    variant: Mapped[str] = mapped_column(String(50), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class UploadSessionModel(AuditColumnsMixin, Base):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        _uuid7_check("id", "id_uuid_v7"),
        CheckConstraint("expected_size >= 0", name="expected_size_non_negative"),
        CheckConstraint(
            "uploaded_bytes >= 0 AND uploaded_bytes <= expected_size",
            name="uploaded_bytes_valid",
        ),
        CheckConstraint(
            "checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_sha256_valid",
        ),
        UniqueConstraint("staging_key", name="uq_upload_sessions_staging_key"),
        Index("ix_upload_sessions_owner_status", "owner_id", "status"),
        Index("ix_upload_sessions_expires_at", "expires_at"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_name: Mapped[str] = mapped_column(String(300), nullable=False)
    expected_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(50), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    staging_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TrashItemModel(Base):
    __tablename__ = "trash_items"
    __table_args__ = (
        _uuid7_check("id", "id_uuid_v7"),
        UniqueConstraint("entry_id", name="uq_trash_items_entry_id"),
        Index("ix_trash_items_deleted_by_trashed", "deleted_by", "trashed_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    entry_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_parent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    deleted_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    trashed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
