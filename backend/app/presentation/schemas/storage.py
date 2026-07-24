"""Pydantic v2 contracts for storage metadata endpoints."""

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.dtos.storage import (
    SortDirection,
    StorageEntryKind,
    StorageSortField,
)

EntryName = Annotated[str, Field(min_length=1, max_length=255)]


class StorageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FolderEntriesQuery(StorageModel):
    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)
    sort_by: StorageSortField = StorageSortField.NAME
    direction: SortDirection = SortDirection.ASC
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: StorageEntryKind | None = None
    extension: str | None = Field(default=None, min_length=1, max_length=50)
    minimum_size: int | None = Field(default=None, ge=0)
    maximum_size: int | None = Field(default=None, ge=0)
    modified_from: datetime | None = None
    modified_to: datetime | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if (
            self.minimum_size is not None
            and self.maximum_size is not None
            and self.minimum_size > self.maximum_size
        ):
            raise ValueError("minimum_size cannot exceed maximum_size")
        if (
            self.modified_from is not None
            and self.modified_to is not None
            and self.modified_from > self.modified_to
        ):
            raise ValueError("modified_from cannot be later than modified_to")
        for value in (self.modified_from, self.modified_to):
            if value is not None and value.tzinfo is None:
                raise ValueError("date filters must include a timezone")
        return self


class CreateFolderInput(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {"parent_id": "019f7769-b2c8-7000-8000-000000000001", "name": "Photos"}
            ]
        },
    )

    parent_id: UUID
    name: EntryName


class RenameEntryInput(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={"examples": [{"name": "Travel photos"}]},
    )

    name: EntryName


class MoveEntryInput(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {"destination_folder_id": "019f7769-b2c8-7000-8000-000000000002"}
            ]
        },
    )

    destination_folder_id: UUID


class CopyEntryInput(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "destination_folder_id": "019f7769-b2c8-7000-8000-000000000002",
                    "name": "Photo copy.jpg",
                }
            ]
        },
    )

    destination_folder_id: UUID
    name: EntryName | None = None


class RestoreTrashInput(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {"destination_folder_id": "019f7769-b2c8-7000-8000-000000000001"}
            ]
        },
    )

    destination_folder_id: UUID | None = None


class StorageEntryData(StorageModel):
    id: UUID
    parent_id: UUID | None
    kind: StorageEntryKind
    name: str
    size: int | None
    mime_type: str | None
    extension: str | None
    checksum_sha256: str | None
    current_version_number: int | None
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False


class FolderEntriesData(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "folder_id": "019f7769-b2c8-7000-8000-000000000001",
                    "items": [
                        {
                            "id": "019f7769-b2c8-7000-8000-000000000003",
                            "parent_id": "019f7769-b2c8-7000-8000-000000000001",
                            "kind": "folder",
                            "name": "Photos",
                            "size": None,
                            "mime_type": None,
                            "extension": None,
                            "checksum_sha256": None,
                            "current_version_number": None,
                            "created_at": "2026-07-18T18:00:00Z",
                            "updated_at": "2026-07-18T18:00:00Z",
                            "is_favorite": False,
                        }
                    ],
                }
            ]
        },
    )

    folder_id: UUID
    items: tuple[StorageEntryData, ...]


class FolderBreadcrumbData(StorageModel):
    id: UUID
    name: str


class FolderNavigationData(StorageModel):
    folder: StorageEntryData
    breadcrumbs: tuple[FolderBreadcrumbData, ...]


class FileDetailsData(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "019f7769-b2c8-7000-8000-000000000004",
                    "parent_id": "019f7769-b2c8-7000-8000-000000000001",
                    "name": "report.pdf",
                    "original_name": "report.pdf",
                    "size": 1048576,
                    "mime_type": "application/pdf",
                    "extension": "pdf",
                    "checksum_sha256": "a" * 64,
                    "current_version_number": 1,
                    "created_at": "2026-07-18T18:00:00Z",
                    "updated_at": "2026-07-18T18:00:00Z",
                }
            ]
        },
    )

    id: UUID
    parent_id: UUID
    name: str
    original_name: str
    size: int
    mime_type: str
    extension: str
    checksum_sha256: str
    current_version_number: int
    created_at: datetime
    updated_at: datetime


class TrashItemData(StorageModel):
    id: UUID
    entry_id: UUID
    original_parent_id: UUID
    trashed_at: datetime


class PermanentDeleteData(StorageModel):
    deleted_entries: int = Field(ge=1)


class StartUploadInput(StorageModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "parent_id": "019f7769-b2c8-7000-8000-000000000001",
                    "filename": "report.pdf",
                    "size": 1048576,
                    "mime_type": "application/pdf",
                }
            ]
        },
    )

    parent_id: UUID
    filename: EntryName
    size: int = Field(ge=0)
    mime_type: str = Field(min_length=3, max_length=255)


class UploadSessionData(StorageModel):
    id: UUID
    parent_id: UUID
    filename: str
    expected_size: int
    uploaded_bytes: int
    declared_mime_type: str | None
    extension: str
    status: str
    expires_at: datetime
    checksum_sha256: str | None


class UploadChunkData(StorageModel):
    upload_id: UUID
    offset: int
    received_bytes: int
    chunk_sha256: str
