from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.application.dtos.auth import BootstrapAdminCommandDTO
from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import OutboxFilterDTO
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
from app.domain.storage.entities import File, FileVersion, StorageObject
from app.domain.storage.enums import StorageObjectStatus
from app.domain.storage.exceptions import InvalidMoveError
from app.infrastructure.config.settings import AppEnvironment, Settings
from app.infrastructure.container import ApplicationContainer
from app.infrastructure.persistence.identifiers import Uuid7Generator
from app.infrastructure.persistence.models.storage import StorageObjectModel

pytestmark = pytest.mark.postgresql

CHECKSUM = "b" * 64


@dataclass(slots=True)
class StorageTestContext:
    container: ApplicationContainer
    owner_id: UUID
    root_id: UUID
    id_generator: Uuid7Generator


@pytest.fixture
async def storage_context(
    migrated_database_url: str,
    clean_storage: None,
) -> AsyncIterator[StorageTestContext]:
    del clean_storage
    settings = Settings(
        environment=AppEnvironment.TEST,
        database_url=migrated_database_url,
        storage_root=Path.cwd().anchor,
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

    yield StorageTestContext(container, admin.id, root_id, id_generator)
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
    return file, storage_object


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
    async with context.container.unit_of_work_factory() as unit_of_work:
        assert (
            await unit_of_work.storage.get_entry(copied.id, include_deleted=True)
            is None
        )
        assert (
            await unit_of_work.storage.get_storage_object(storage_object.id) is not None
        )
        events = await unit_of_work.outbox.list(
            filters=OutboxFilterDTO(event_type="storage.orphan_sweep_requested"),
            page=PageRequestDTO(limit=10),
        )
    assert len(events.items) == 1
    assert events.items[0].aggregate_id == copied.id
