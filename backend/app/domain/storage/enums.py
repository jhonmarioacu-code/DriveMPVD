"""Stable storage domain enumerations."""

from enum import StrEnum


class EntryType(StrEnum):
    FOLDER = "folder"
    FILE = "file"


class StorageObjectStatus(StrEnum):
    STAGING = "staging"
    READY = "ready"
    DELETING = "deleting"
    QUARANTINED = "quarantined"


class DerivedAssetStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class UploadStatus(StrEnum):
    CREATED = "created"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
