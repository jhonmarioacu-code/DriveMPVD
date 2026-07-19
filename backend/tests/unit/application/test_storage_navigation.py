from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID, uuid4

import pytest

from app.application.exceptions import StorageEntryNotFoundError
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.storage.queries import GetFolderNavigationUseCase
from app.domain.storage.entities import Folder


class FakeStorage:
    def __init__(self, path: tuple[Folder, ...]) -> None:
        self._path = path
        self.owner_id: UUID | None = None
        self.folder_id: UUID | None = None

    async def get_folder_path(
        self,
        *,
        owner_id: UUID,
        folder_id: UUID | None,
    ) -> tuple[Folder, ...]:
        self.owner_id = owner_id
        self.folder_id = folder_id
        return self._path


class FakeUnitOfWork:
    def __init__(self, storage: FakeStorage) -> None:
        self.storage = storage

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeUnitOfWorkFactory:
    def __init__(self, unit_of_work: FakeUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def __call__(self) -> FakeUnitOfWork:
        return self._unit_of_work


def _folder(
    folder_id: UUID,
    owner_id: UUID,
    parent_id: UUID | None,
    name: str,
) -> Folder:
    now = datetime(2026, 7, 18, 18, tzinfo=UTC)
    return Folder(
        id=folder_id,
        owner_id=owner_id,
        parent_id=parent_id,
        name=name,
        normalized_name=name.casefold(),
        created_at=now,
        updated_at=now,
    )


async def test_navigation_returns_root_to_current_folder_path() -> None:
    owner_id = uuid4()
    root = _folder(uuid4(), owner_id, None, "Drive")
    child = _folder(uuid4(), owner_id, root.id, "Photos")
    storage = FakeStorage((root, child))
    use_case = GetFolderNavigationUseCase(
        cast(UnitOfWorkFactory, FakeUnitOfWorkFactory(FakeUnitOfWork(storage)))
    )

    result = await use_case.execute(owner_id=owner_id, folder_id=child.id)

    assert tuple(item.id for item in result) == (root.id, child.id)
    assert storage.owner_id == owner_id
    assert storage.folder_id == child.id


async def test_navigation_rejects_an_unknown_or_inaccessible_folder() -> None:
    use_case = GetFolderNavigationUseCase(
        cast(
            UnitOfWorkFactory,
            FakeUnitOfWorkFactory(FakeUnitOfWork(FakeStorage(()))),
        )
    )

    with pytest.raises(StorageEntryNotFoundError):
        await use_case.execute(owner_id=uuid4(), folder_id=uuid4())
