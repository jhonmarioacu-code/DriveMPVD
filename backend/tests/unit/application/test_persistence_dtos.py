from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.dtos.common import PageRequestDTO
from app.application.dtos.outbox import (
    NewOutboxMessageDTO,
    OutboxCursorDTO,
    OutboxFilterDTO,
)
from app.application.exceptions import ApplicationValidationError


def test_page_request_accepts_bounded_limits() -> None:
    assert PageRequestDTO(limit=1).limit == 1
    assert PageRequestDTO(limit=200).limit == 200


@pytest.mark.parametrize("limit", [0, 201])
def test_page_request_rejects_unbounded_limits(limit: int) -> None:
    with pytest.raises(ApplicationValidationError):
        PageRequestDTO(limit=limit)


def test_new_outbox_message_validates_timezone_and_names() -> None:
    naive = datetime.now(UTC).replace(tzinfo=None)
    valid = NewOutboxMessageDTO(
        aggregate_id=uuid4(),
        aggregate_type="catalog.entry",
        event_type="entry.created",
        occurred_at=datetime.now(UTC),
        payload={"name": "document.pdf"},
    )

    assert valid.payload == {"name": "document.pdf"}

    with pytest.raises(ApplicationValidationError):
        NewOutboxMessageDTO(
            aggregate_id=uuid4(),
            aggregate_type=" ",
            event_type="entry.created",
            occurred_at=datetime.now(UTC),
            payload={},
        )

    with pytest.raises(ApplicationValidationError):
        NewOutboxMessageDTO(
            aggregate_id=uuid4(),
            aggregate_type="catalog.entry",
            event_type="entry.created",
            occurred_at=naive,
            payload={},
        )


def test_outbox_filter_and_cursor_require_consistent_aware_dates() -> None:
    now = datetime.now(UTC)
    naive = now.replace(tzinfo=None)
    assert OutboxCursorDTO(created_at=now, id=uuid4()).created_at == now
    assert OutboxFilterDTO(created_from=now, created_to=now).pending_only

    with pytest.raises(ApplicationValidationError):
        OutboxCursorDTO(created_at=naive, id=uuid4())

    with pytest.raises(ApplicationValidationError):
        OutboxFilterDTO(created_from=naive)

    with pytest.raises(ApplicationValidationError):
        OutboxFilterDTO(created_to=naive)

    with pytest.raises(ApplicationValidationError):
        OutboxFilterDTO(
            created_from=datetime(2026, 7, 19, tzinfo=UTC),
            created_to=datetime(2026, 7, 18, tzinfo=UTC),
        )
