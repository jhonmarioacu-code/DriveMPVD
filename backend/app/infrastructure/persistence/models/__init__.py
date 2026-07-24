"""SQLAlchemy models; never exported as domain entities."""

from app.infrastructure.persistence.models.activity import (
    FavoriteModel,
    RecentOpenModel,
)
from app.infrastructure.persistence.models.auth import (
    AdminAccountModel,
    AuthRateLimitModel,
    AuthSessionModel,
    SecurityEventModel,
)
from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.models.outbox import OutboxEventModel
from app.infrastructure.persistence.models.storage import (
    FileMetadataModel,
    FileVersionModel,
    PreviewModel,
    StorageEntryModel,
    StorageObjectModel,
    ThumbnailModel,
    TrashItemModel,
    UploadSessionModel,
)

__all__ = [
    "AdminAccountModel",
    "AuthRateLimitModel",
    "AuthSessionModel",
    "Base",
    "FavoriteModel",
    "FileMetadataModel",
    "FileVersionModel",
    "OutboxEventModel",
    "PreviewModel",
    "RecentOpenModel",
    "SecurityEventModel",
    "StorageEntryModel",
    "StorageObjectModel",
    "ThumbnailModel",
    "TrashItemModel",
    "UploadSessionModel",
]
