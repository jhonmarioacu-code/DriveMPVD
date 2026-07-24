"""Transactional use cases for private favorites and recent opens."""

import base64
import binascii
import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.application.dtos.activity import (
    ActivityCursorDTO,
    ActivityEntryDTO,
    FavoriteStatusDTO,
    ListActivityQueryDTO,
    RecordRecentOpenCommandDTO,
)
from app.application.dtos.common import PageDTO
from app.application.exceptions import (
    ApplicationValidationError,
    StorageEntryNotFoundError,
)
from app.application.ports.auth_services import Clock
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.storage.mappers import entry_to_dto
from app.domain.storage.entities import StorageEntry

ActivityKind = Literal["favorites", "recents"]


class ActivityUseCase:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    @staticmethod
    def _require_owned(
        entry: StorageEntry | None,
        owner_id: UUID,
    ) -> StorageEntry:
        if entry is None or entry.owner_id != owner_id:
            raise StorageEntryNotFoundError()
        return entry


class SetFavoriteUseCase(ActivityUseCase):
    async def execute(self, *, owner_id: UUID, entry_id: UUID) -> FavoriteStatusDTO:
        async with self._unit_of_work_factory() as unit_of_work:
            self._require_owned(
                await unit_of_work.storage.get_entry(entry_id, for_update=True),
                owner_id,
            )
            await unit_of_work.activity.add_favorite(
                owner_id=owner_id,
                entry_id=entry_id,
                created_at=self._clock.now(),
            )
            await unit_of_work.commit()
        return FavoriteStatusDTO(entry_id=entry_id, is_favorite=True)


class RemoveFavoriteUseCase(ActivityUseCase):
    async def execute(self, *, owner_id: UUID, entry_id: UUID) -> FavoriteStatusDTO:
        async with self._unit_of_work_factory() as unit_of_work:
            self._require_owned(
                await unit_of_work.storage.get_entry(entry_id, for_update=True),
                owner_id,
            )
            await unit_of_work.activity.remove_favorite(
                owner_id=owner_id,
                entry_id=entry_id,
            )
            await unit_of_work.commit()
        return FavoriteStatusDTO(entry_id=entry_id, is_favorite=False)


class RecordRecentOpenUseCase(ActivityUseCase):
    async def execute(self, command: RecordRecentOpenCommandDTO) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            self._require_owned(
                await unit_of_work.storage.get_entry(command.entry_id, for_update=True),
                command.owner_id,
            )
            await unit_of_work.activity.record_recent_open(
                owner_id=command.owner_id,
                entry_id=command.entry_id,
                opened_at=self._clock.now(),
            )
            await unit_of_work.commit()


class ListActivityUseCase(ActivityUseCase):
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
        *,
        kind: ActivityKind,
    ) -> None:
        super().__init__(unit_of_work_factory, clock)
        self._kind = kind

    async def execute(
        self,
        query: ListActivityQueryDTO,
    ) -> PageDTO[ActivityEntryDTO]:
        if not 1 <= query.limit <= 200:
            raise ApplicationValidationError("Page limit must be between 1 and 200.")
        cursor = _decode_cursor(query.cursor, self._kind)
        async with self._unit_of_work_factory() as unit_of_work:
            if self._kind == "favorites":
                records, has_more = await unit_of_work.activity.list_favorites(
                    owner_id=query.owner_id,
                    limit=query.limit,
                    cursor=cursor,
                )
            else:
                records, has_more = await unit_of_work.activity.list_recents(
                    owner_id=query.owner_id,
                    limit=query.limit,
                    cursor=cursor,
                )
        items = tuple(
            ActivityEntryDTO(
                entry=entry_to_dto(record.entry, is_favorite=record.is_favorite),
                occurred_at=record.occurred_at,
            )
            for record in records
        )
        next_cursor = (
            _encode_cursor(items[-1], self._kind) if has_more and items else None
        )
        return PageDTO(items=items, next_cursor=next_cursor)


def _encode_cursor(entry: ActivityEntryDTO, kind: ActivityKind) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "kind": kind,
            "at": entry.occurred_at.isoformat(),
            "id": str(entry.entry.id),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(raw: str | None, kind: ActivityKind) -> ActivityCursorDTO | None:
    if raw is None:
        return None
    try:
        padding = "=" * (-len(raw) % 4)
        value = json.loads(base64.urlsafe_b64decode(f"{raw}{padding}"))
        if (
            not isinstance(value, dict)
            or value.get("v") != 1
            or value.get("kind") != kind
        ):
            raise ValueError
        occurred_at = datetime.fromisoformat(str(value["at"]))
        if occurred_at.tzinfo is None:
            raise ValueError
        entry_id = UUID(str(value["id"]))
    except (KeyError, TypeError, ValueError, binascii.Error) as exc:
        raise ApplicationValidationError("Activity cursor is invalid.") from exc
    return ActivityCursorDTO(occurred_at=occurred_at, entry_id=entry_id)
