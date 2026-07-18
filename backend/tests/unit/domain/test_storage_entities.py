from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.storage.entities import (
    File,
    FileVersion,
    Folder,
    Preview,
    StorageObject,
    Thumbnail,
    TrashItem,
    UploadSession,
)
from app.domain.storage.enums import (
    DerivedAssetStatus,
    EntryType,
    StorageObjectStatus,
    UploadStatus,
)
from app.domain.storage.exceptions import (
    InvalidChecksumError,
    InvalidEntryNameError,
    InvalidStateTransitionError,
)
from app.domain.storage.value_objects import EntryName, Sha256Checksum

NOW = datetime(2026, 7, 18, tzinfo=UTC)
CHECKSUM = "a" * 64


def _folder(*, parent: bool = True) -> Folder:
    return Folder(
        id=uuid4(),
        owner_id=uuid4(),
        parent_id=uuid4() if parent else None,
        name="Documents",
        normalized_name="documents",
        created_at=NOW,
        updated_at=NOW,
    )


def _file() -> File:
    return File(
        id=uuid4(),
        owner_id=uuid4(),
        parent_id=uuid4(),
        name="Report.PDF",
        normalized_name="report.pdf",
        created_at=NOW,
        updated_at=NOW,
        original_name="Report.PDF",
        internal_name="object.pdf",
        size=42,
        mime_type="application/pdf",
        extension="pdf",
        checksum_sha256=CHECKSUM,
    )


def test_entry_name_normalizes_and_extracts_extension() -> None:
    value = EntryName.create("  RéPORT.PDF  ")

    assert value.value == "RéPORT.PDF"
    assert value.normalized == "réport.pdf"
    assert value.extension == "pdf"


@pytest.mark.parametrize(
    "value",
    ["", "   ", ".", "..", "path/file", "path\\file", "a\x00b", "a\nb", "x" * 256],
)
def test_entry_name_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(InvalidEntryNameError):
        EntryName.create(value)


def test_checksum_canonicalizes_valid_sha256() -> None:
    assert Sha256Checksum.create(CHECKSUM).value == CHECKSUM
    assert Sha256Checksum.create("A" * 64).value == CHECKSUM
    for invalid in ("", "z" * 64, "a" * 63):
        with pytest.raises(InvalidChecksumError):
            Sha256Checksum.create(invalid)


def test_entry_lifecycle_preserves_tree_and_audit_invariants() -> None:
    folder = _folder()
    renamed_at = NOW + timedelta(seconds=1)
    moved_at = NOW + timedelta(seconds=2)
    trashed_at = NOW + timedelta(seconds=3)
    restored_at = NOW + timedelta(seconds=4)
    destination = uuid4()

    folder.rename(EntryName.create("Photos"), now=renamed_at)
    folder.move(destination, now=moved_at)
    folder.move_to_trash(now=trashed_at)

    assert (folder.name, folder.normalized_name) == ("Photos", "photos")
    assert folder.parent_id == destination
    assert folder.deleted_at == trashed_at
    with pytest.raises(InvalidStateTransitionError):
        folder.rename(EntryName.create("Blocked"), now=trashed_at)
    with pytest.raises(InvalidStateTransitionError):
        folder.move(uuid4(), now=trashed_at)

    restored_parent = uuid4()
    folder.restore(parent_id=restored_parent, now=restored_at)
    assert folder.parent_id == restored_parent
    assert folder.deleted_at is None
    assert folder.updated_at == restored_at
    with pytest.raises(InvalidStateTransitionError):
        folder.restore(parent_id=restored_parent, now=restored_at)


def test_root_cannot_be_trashed() -> None:
    with pytest.raises(InvalidStateTransitionError):
        _folder(parent=False).move_to_trash(now=NOW)


def test_file_and_immutable_object_metadata_are_validated() -> None:
    file = _file()
    object_id = uuid4()
    storage_object = StorageObject(
        id=object_id,
        storage_key="objects/ab/content",
        size=file.size,
        mime_type=file.mime_type,
        checksum_sha256=file.checksum_sha256,
        status=StorageObjectStatus.READY,
        created_at=NOW,
        updated_at=NOW,
    )
    version = FileVersion(
        id=uuid4(),
        file_id=file.id,
        storage_object_id=object_id,
        version_number=1,
        original_name=file.original_name,
        size=file.size,
        mime_type=file.mime_type,
        extension=file.extension,
        checksum_sha256=file.checksum_sha256,
        created_by=file.owner_id,
        created_at=NOW,
    )

    assert file.entry_type is EntryType.FILE
    assert storage_object.status is StorageObjectStatus.READY
    assert version.storage_object_id == storage_object.id

    with pytest.raises(InvalidStateTransitionError):
        replace(file, size=-1)


@pytest.mark.parametrize("kind", ["file", "object", "version"])
def test_content_entities_reject_inconsistent_metadata(kind: str) -> None:
    if kind == "file":
        file = _file()
        file.size = -1
        with pytest.raises(InvalidStateTransitionError):
            file.__post_init__()
    elif kind == "object":
        with pytest.raises(InvalidStateTransitionError):
            StorageObject(
                id=uuid4(),
                storage_key="",
                size=0,
                mime_type="text/plain",
                checksum_sha256=CHECKSUM,
                status=StorageObjectStatus.STAGING,
                created_at=NOW,
                updated_at=NOW,
            )
    else:
        with pytest.raises(InvalidStateTransitionError):
            FileVersion(
                id=uuid4(),
                file_id=uuid4(),
                storage_object_id=uuid4(),
                version_number=0,
                original_name="a.txt",
                size=0,
                mime_type="text/plain",
                extension="txt",
                checksum_sha256=CHECKSUM,
                created_by=uuid4(),
                created_at=NOW,
            )


def test_upload_session_requires_monotonic_complete_progress() -> None:
    upload = UploadSession(
        id=uuid4(),
        owner_id=uuid4(),
        parent_id=uuid4(),
        original_name="video.mp4",
        internal_name="staging.mp4",
        expected_size=100,
        uploaded_bytes=0,
        mime_type="video/mp4",
        extension="mp4",
        checksum_sha256=None,
        staging_key="staging/session",
        status=UploadStatus.CREATED,
        expires_at=NOW + timedelta(days=1),
        created_at=NOW,
        updated_at=NOW,
    )

    upload.record_progress(persisted_offset=50, now=NOW + timedelta(seconds=1))
    with pytest.raises(InvalidStateTransitionError):
        upload.record_progress(persisted_offset=49, now=NOW)
    with pytest.raises(InvalidStateTransitionError):
        upload.complete(checksum=Sha256Checksum.create(CHECKSUM), now=NOW)

    upload.record_progress(persisted_offset=100, now=NOW + timedelta(seconds=2))
    upload.complete(checksum=Sha256Checksum.create(CHECKSUM), now=NOW)
    assert upload.status is UploadStatus.COMPLETED
    assert upload.checksum_sha256 == CHECKSUM
    with pytest.raises(InvalidStateTransitionError):
        upload.record_progress(persisted_offset=100, now=NOW)


def test_future_domain_records_are_provider_independent() -> None:
    version_id = uuid4()
    thumbnail = Thumbnail(
        id=uuid4(),
        file_version_id=version_id,
        storage_object_id=None,
        variant="small",
        width=256,
        height=256,
        status=DerivedAssetStatus.PENDING,
        created_at=NOW,
        updated_at=NOW,
    )
    preview = Preview(
        id=uuid4(),
        file_version_id=version_id,
        storage_object_id=None,
        variant="browser",
        mime_type=None,
        status=DerivedAssetStatus.PENDING,
        created_at=NOW,
        updated_at=NOW,
    )
    trash = TrashItem(
        id=uuid4(),
        entry_id=uuid4(),
        original_parent_id=uuid4(),
        deleted_by=uuid4(),
        trashed_at=NOW,
    )

    assert thumbnail.file_version_id == preview.file_version_id
    assert trash.trashed_at == NOW
