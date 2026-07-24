import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select, text

from app.application.dtos.auth import BootstrapAdminCommandDTO
from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import (
    NewOutboxMessageDTO,
    OutboxFilterDTO,
    ProcessStorageOutboxCommandDTO,
)
from app.application.dtos.storage import (
    CopyEntryCommandDTO,
    CreateFolderCommandDTO,
    MoveEntryCommandDTO,
    PermanentlyDeleteCommandDTO,
    RenameEntryCommandDTO,
    RestoreEntryCommandDTO,
    StorageEntryKind,
    TrashEntryCommandDTO,
)
from app.application.exceptions import StorageNameConflictError
from app.application.ports.file_storage import StorageKey
from app.application.use_cases.storage.outbox import (
    OBJECT_DELETE_REQUESTED_EVENT,
    ORPHAN_SWEEP_REQUESTED_EVENT,
)
from app.domain.storage.entities import File, FileVersion, StorageObject
from app.domain.storage.enums import StorageObjectStatus
from app.domain.storage.exceptions import InvalidMoveError
from app.infrastructure.config.settings import AppEnvironment, Settings
from app.infrastructure.container import ApplicationContainer
from app.infrastructure.persistence.identifiers import Uuid7Generator
from app.infrastructure.persistence.models.storage import (
    PreviewModel,
    StorageObjectModel,
    ThumbnailModel,
)

pytestmark = pytest.mark.postgresql

CHECKSUM = "b" * 64


@dataclass(slots=True)
class StorageTestContext:
    container: ApplicationContainer
    owner_id: UUID
    root_id: UUID
    id_generator: Uuid7Generator
    storage_root: Path


@pytest.fixture
async def storage_context(
    migrated_database_url: str,
    clean_storage: None,
    tmp_path: Path,
) -> AsyncIterator[StorageTestContext]:
    del clean_storage
    storage_root = tmp_path / "storage"
    settings = Settings(
        environment=AppEnvironment.TEST,
        database_url=migrated_database_url,
        storage_root=storage_root,
        database_pool_size=2,
        database_max_overflow=0,
        argon2_time_cost=1,
        argon2_memory_cost_kib=19_456,
        argon2_parallelism=1,
        jwt_access_secret="a" * 40,
        jwt_refresh_secret="b" * 40,
        auth_secret_pepper="c" * 40,
    )
    container = ApplicationContainer.build(settings)
    admin = await container.bootstrap_admin.execute(
        BootstrapAdminCommandDTO(
            username="Admin",
            password="correct horse battery staple",
        )
    )
    id_generator = Uuid7Generator()
    async with container.unit_of_work_factory() as unit_of_work:
        path = await unit_of_work.storage.get_folder_path(
            owner_id=admin.id,
            folder_id=None,
        )
    root_id = path[-1].id

    yield StorageTestContext(container, admin.id, root_id, id_generator, storage_root)
    await container.database.dispose()


async def _add_file(
    context: StorageTestContext,
    *,
    parent_id: UUID,
    name: str = "report.pdf",
) -> tuple[File, StorageObject]:
    id_generator = context.id_generator
    now = datetime.now(UTC)
    file_id = id_generator.new()
    object_id = id_generator.new()
    storage_object = StorageObject(
        id=object_id,
        storage_key=f"objects/{object_id}",
        size=1024,
        mime_type="application/pdf",
        checksum_sha256=CHECKSUM,
        status=StorageObjectStatus.READY,
        created_at=now,
        updated_at=now,
    )
    file = File(
        id=file_id,
        owner_id=context.owner_id,
        parent_id=parent_id,
        name=name,
        normalized_name=name.casefold(),
        original_name=name,
        internal_name=f"{file_id}.pdf",
        size=storage_object.size,
        mime_type=storage_object.mime_type,
        extension="pdf",
        checksum_sha256=storage_object.checksum_sha256,
        current_version_number=1,
        created_at=now,
        updated_at=now,
    )
    version = FileVersion(
        id=id_generator.new(),
        file_id=file.id,
        storage_object_id=storage_object.id,
        version_number=1,
        original_name=file.original_name,
        size=file.size,
        mime_type=file.mime_type,
        extension=file.extension,
        checksum_sha256=file.checksum_sha256,
        created_by=context.owner_id,
        created_at=now,
    )
    async with context.container.unit_of_work_factory() as unit_of_work:
        await unit_of_work.storage.add_storage_object(storage_object)
        await unit_of_work.storage.add_file(file, version)
        await unit_of_work.commit()
    await asyncio.to_thread(
        _write_storage_object,
        context.storage_root / storage_object.storage_key,
        storage_object.size,
    )
    return file, storage_object


def _write_storage_object(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


async def test_folder_commands_enforce_names_and_prevent_cycles(
    storage_context: StorageTestContext,
) -> None:
    context = storage_context
    first = await context.container.create_folder.execute(
        CreateFolderCommandDTO(context.owner_id, context.root_id, "Documents")
    )
    second = await context.container.create_folder.execute(
        CreateFolderCommandDTO(context.owner_id, context.root_id, "Photos")
    )
    child = await context.container.create_folder.execute(
        CreateFolderCommandDTO(context.owner_id, first.id, "Drafts")
    )

    renamed = await context.container.rename_entry.execute(
        RenameEntryCommandDTO(context.owner_id, child.id, "Final")
    )
    assert renamed.name == "Final"
    with pytest.raises(StorageNameConflictError):
        await context.container.rename_entry.execute(
            RenameEntryCommandDTO(context.owner_id, first.id, "Photos")
        )
    with pytest.raises(InvalidMoveError):
        await context.container.move_entry.execute(
            MoveEntryCommandDTO(context.owner_id, first.id, child.id)
        )

    moved = await context.container.move_entry.execute(
        MoveEntryCommandDTO(context.owner_id, child.id, second.id)
    )
    assert moved.parent_id == second.id
    async with context.container.unit_of_work_factory() as unit_of_work:
        tree = [
            node async for node in unit_of_work.storage.stream_subtree(context.root_id)
        ]
    assert [(node.entry.name, node.depth) for node in tree] == [
        ("Drive", 0),
        ("Documents", 1),
        ("Photos", 1),
        ("Final", 2),
    ]


async def test_orphan_sweep_reference_indexes_are_migrated(
    storage_context: StorageTestContext,
) -> None:
    async with storage_context.container.database.engine.connect() as connection:
        indexes = set(
            await connection.scalars(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = current_schema() "
                    "AND indexname IN ("
                    "'ix_storage_objects_status_created_id', "
                    "'ix_thumbnails_storage_object_id', "
                    "'ix_previews_storage_object_id'"
                    ")"
                )
            )
        )
    assert indexes == {
        "ix_storage_objects_status_created_id",
        "ix_thumbnails_storage_object_id",
        "ix_previews_storage_object_id",
    }


async def test_copy_file_reuses_immutable_object_without_deduplicating(
    storage_context: StorageTestContext,
) -> None:
    context = storage_context
    source, storage_object = await _add_file(context, parent_id=context.root_id)
    destination = await context.container.create_folder.execute(
        CreateFolderCommandDTO(context.owner_id, context.root_id, "Copies")
    )

    copied = await context.container.copy_entry.execute(
        CopyEntryCommandDTO(
            context.owner_id,
            source.id,
            destination.id,
            "report-copy.pdf",
        )
    )

    assert copied.kind is StorageEntryKind.FILE
    async with context.container.unit_of_work_factory() as unit_of_work:
        copied_entry = await unit_of_work.storage.get_entry(copied.id)
        version = await unit_of_work.storage.get_current_version(copied.id)
        loaded_object = await unit_of_work.storage.get_storage_object(storage_object.id)
    assert isinstance(copied_entry, File)
    assert copied_entry.internal_name != source.internal_name
    assert version is not None
    assert version.storage_object_id == storage_object.id
    assert loaded_object == storage_object
    async with context.container.database.session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(StorageObjectModel))
            == 1
        )


async def test_recursive_copy_trash_restore_and_permanent_deletion_are_atomic(
    storage_context: StorageTestContext,
) -> None:
    context = storage_context
    source = await context.container.create_folder.execute(
        CreateFolderCommandDTO(context.owner_id, context.root_id, "Project")
    )
    child = await context.container.create_folder.execute(
        CreateFolderCommandDTO(context.owner_id, source.id, "Assets")
    )
    _, storage_object = await _add_file(context, parent_id=child.id, name="design.pdf")

    copied = await context.container.copy_entry.execute(
        CopyEntryCommandDTO(
            context.owner_id,
            source.id,
            context.root_id,
            "Project copy",
        )
    )
    async with context.container.unit_of_work_factory() as unit_of_work:
        copied_tree = [
            node async for node in unit_of_work.storage.stream_subtree(copied.id)
        ]
    assert [(node.entry.name, node.depth) for node in copied_tree] == [
        ("Project copy", 0),
        ("Assets", 1),
        ("design.pdf", 2),
    ]

    trash_item = await context.container.trash_entry.execute(
        TrashEntryCommandDTO(context.owner_id, copied.id)
    )
    async with context.container.unit_of_work_factory() as unit_of_work:
        assert await unit_of_work.storage.get_entry(copied.id) is None
        assert await unit_of_work.storage.get_entry(copied_tree[-1].entry.id) is None

    restored = await context.container.restore_entry.execute(
        RestoreEntryCommandDTO(context.owner_id, trash_item.id)
    )
    assert restored.parent_id == context.root_id
    async with context.container.unit_of_work_factory() as unit_of_work:
        assert (
            await unit_of_work.storage.get_entry(copied_tree[-1].entry.id) is not None
        )

    second_trash = await context.container.trash_entry.execute(
        TrashEntryCommandDTO(context.owner_id, copied.id)
    )
    deleted_count = await context.container.permanently_delete.execute(
        PermanentlyDeleteCommandDTO(context.owner_id, second_trash.id)
    )
    assert deleted_count.deleted_entries == 3
    retained_result = await context.container.process_storage_outbox.execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=10, orphan_batch_size=10)
    )
    assert retained_result.events_processed == 1
    assert retained_result.metadata_objects_deleted == 0
    assert retained_result.physical_objects_deleted == 0
    async with context.container.unit_of_work_factory() as unit_of_work:
        assert (
            await unit_of_work.storage.get_entry(copied.id, include_deleted=True)
            is None
        )
        assert (
            await unit_of_work.storage.get_storage_object(storage_object.id) is not None
        )
        events = await unit_of_work.outbox.list(
            filters=OutboxFilterDTO(
                event_type=ORPHAN_SWEEP_REQUESTED_EVENT,
                pending_only=False,
            ),
            page=PageRequestDTO(limit=10),
        )
    assert len(events.items) == 1
    assert events.items[0].aggregate_id == copied.id
    assert events.items[0].processed_at is not None
    assert (
        await context.container.file_storage.stat(
            StorageKey(storage_object.storage_key)
        )
        is not None
    )

    source_trash = await context.container.trash_entry.execute(
        TrashEntryCommandDTO(context.owner_id, source.id)
    )
    source_deleted = await context.container.permanently_delete.execute(
        PermanentlyDeleteCommandDTO(context.owner_id, source_trash.id)
    )
    assert source_deleted.deleted_entries == 3
    deleted_result = await context.container.process_storage_outbox.execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=10, orphan_batch_size=10)
    )
    assert deleted_result.events_processed == 2
    assert deleted_result.metadata_objects_deleted == 1
    assert deleted_result.physical_objects_deleted == 1
    async with context.container.unit_of_work_factory() as unit_of_work:
        assert await unit_of_work.storage.get_storage_object(storage_object.id) is None
        sweeps = await unit_of_work.outbox.list(
            filters=OutboxFilterDTO(
                event_type=ORPHAN_SWEEP_REQUESTED_EVENT,
                pending_only=False,
            ),
            page=PageRequestDTO(limit=10),
        )
        physical_deletes = await unit_of_work.outbox.list(
            filters=OutboxFilterDTO(
                event_type=OBJECT_DELETE_REQUESTED_EVENT,
                pending_only=False,
            ),
            page=PageRequestDTO(limit=10),
        )
    assert len(sweeps.items) == 2
    assert all(event.processed_at is not None for event in sweeps.items)
    assert len(physical_deletes.items) == 1
    assert physical_deletes.items[0].processed_at is not None
    assert (
        await context.container.file_storage.stat(
            StorageKey(storage_object.storage_key)
        )
        is None
    )


async def test_orphan_sweep_retains_objects_referenced_only_by_derived_assets(
    storage_context: StorageTestContext,
) -> None:
    context = storage_context
    file, _ = await _add_file(context, parent_id=context.root_id)
    now = datetime.now(UTC)
    thumbnail_object_id = context.id_generator.new()
    preview_object_id = context.id_generator.new()
    thumbnail_object = StorageObject(
        id=thumbnail_object_id,
        storage_key=f"objects/{thumbnail_object_id}",
        size=32,
        mime_type="image/jpeg",
        checksum_sha256=CHECKSUM,
        status=StorageObjectStatus.READY,
        created_at=now,
        updated_at=now,
    )
    preview_object = StorageObject(
        id=preview_object_id,
        storage_key=f"objects/{preview_object_id}",
        size=64,
        mime_type="application/pdf",
        checksum_sha256=CHECKSUM,
        status=StorageObjectStatus.READY,
        created_at=now,
        updated_at=now,
    )
    async with context.container.unit_of_work_factory() as unit_of_work:
        version = await unit_of_work.storage.get_current_version(file.id)
    assert version is not None
    async with context.container.database.session_factory() as session, session.begin():
        session.add_all(
            [
                StorageObjectModel(
                    id=thumbnail_object.id,
                    storage_key=thumbnail_object.storage_key,
                    size=thumbnail_object.size,
                    mime_type=thumbnail_object.mime_type,
                    checksum_sha256=thumbnail_object.checksum_sha256,
                    status=thumbnail_object.status.value,
                    created_at=thumbnail_object.created_at,
                    updated_at=thumbnail_object.updated_at,
                ),
                StorageObjectModel(
                    id=preview_object.id,
                    storage_key=preview_object.storage_key,
                    size=preview_object.size,
                    mime_type=preview_object.mime_type,
                    checksum_sha256=preview_object.checksum_sha256,
                    status=preview_object.status.value,
                    created_at=preview_object.created_at,
                    updated_at=preview_object.updated_at,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                ThumbnailModel(
                    id=context.id_generator.new(),
                    file_version_id=version.id,
                    storage_object_id=thumbnail_object.id,
                    variant="small",
                    width=10,
                    height=10,
                    status="ready",
                ),
                PreviewModel(
                    id=context.id_generator.new(),
                    file_version_id=version.id,
                    storage_object_id=preview_object.id,
                    variant="document",
                    mime_type="application/pdf",
                    status="ready",
                ),
            ]
        )
    await asyncio.gather(
        asyncio.to_thread(
            _write_storage_object,
            context.storage_root / thumbnail_object.storage_key,
            thumbnail_object.size,
        ),
        asyncio.to_thread(
            _write_storage_object,
            context.storage_root / preview_object.storage_key,
            preview_object.size,
        ),
    )
    async with context.container.unit_of_work_factory() as unit_of_work:
        await unit_of_work.outbox.add(
            NewOutboxMessageDTO(
                aggregate_id=file.id,
                aggregate_type="storage.entry",
                event_type=ORPHAN_SWEEP_REQUESTED_EVENT,
                occurred_at=now,
                payload={"reason": "derived-reference-regression"},
            )
        )
        await unit_of_work.commit()

    result = await context.container.process_storage_outbox.execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=10, orphan_batch_size=10)
    )

    assert result.events_processed == 1
    assert result.metadata_objects_deleted == 0
    assert result.physical_objects_deleted == 0
    async with context.container.unit_of_work_factory() as unit_of_work:
        assert await unit_of_work.storage.get_storage_object(thumbnail_object.id)
        assert await unit_of_work.storage.get_storage_object(preview_object.id)
    assert (
        await context.container.file_storage.stat(
            StorageKey(thumbnail_object.storage_key)
        )
        is not None
    )
    assert (
        await context.container.file_storage.stat(
            StorageKey(preview_object.storage_key)
        )
        is not None
    )


async def test_orphan_sweep_commits_metadata_event_before_physical_deletion(
    storage_context: StorageTestContext,
) -> None:
    context = storage_context
    file, storage_object = await _add_file(context, parent_id=context.root_id)
    trash_item = await context.container.trash_entry.execute(
        TrashEntryCommandDTO(context.owner_id, file.id)
    )
    await context.container.permanently_delete.execute(
        PermanentlyDeleteCommandDTO(context.owner_id, trash_item.id)
    )

    scheduled = await context.container.process_storage_outbox.execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=1, orphan_batch_size=10)
    )

    assert scheduled.events_processed == 1
    assert scheduled.metadata_objects_deleted == 1
    assert scheduled.physical_objects_deleted == 0
    async with context.container.unit_of_work_factory() as unit_of_work:
        assert await unit_of_work.storage.get_storage_object(storage_object.id) is None
        delete_events = await unit_of_work.outbox.list(
            filters=OutboxFilterDTO(
                event_type=OBJECT_DELETE_REQUESTED_EVENT,
                pending_only=True,
            ),
            page=PageRequestDTO(limit=10),
        )
    assert len(delete_events.items) == 1
    assert (
        await context.container.file_storage.stat(
            StorageKey(storage_object.storage_key)
        )
        is not None
    )

    delivered = await context.container.process_storage_outbox.execute(
        ProcessStorageOutboxCommandDTO(event_batch_size=1, orphan_batch_size=10)
    )

    assert delivered.events_processed == 1
    assert delivered.physical_objects_deleted == 1
    assert (
        await context.container.file_storage.stat(
            StorageKey(storage_object.storage_key)
        )
        is None
    )
