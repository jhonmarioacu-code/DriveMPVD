"""ORM mappings for private favorites and recent entry opens."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class FavoriteModel(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        Index("ix_favorites_owner_created_entry", "owner_id", "created_at", "entry_id"),
        Index("ix_favorites_entry_id", "entry_id"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entry_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class RecentOpenModel(Base):
    __tablename__ = "recent_opens"
    __table_args__ = (
        CheckConstraint("open_count >= 1", name="open_count_positive"),
        Index(
            "ix_recent_opens_owner_opened_entry", "owner_id", "opened_at", "entry_id"
        ),
        Index("ix_recent_opens_entry_id", "entry_id"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entry_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("storage_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
