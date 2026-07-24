import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.dtos.outbox import (
    ProcessStorageOutboxCommandDTO,
    ProcessStorageOutboxResultDTO,
)
from app.infrastructure.cli import process_storage_outbox
from app.infrastructure.container import ApplicationContainer


@dataclass
class FakeDatabase:
    disposed: bool = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeProcessor:
    def __init__(self, result: ProcessStorageOutboxResultDTO) -> None:
        self.result = result
        self.commands: list[ProcessStorageOutboxCommandDTO] = []

    async def execute(
        self,
        command: ProcessStorageOutboxCommandDTO,
    ) -> ProcessStorageOutboxResultDTO:
        self.commands.append(command)
        return self.result


@dataclass
class FakeContainer:
    process_storage_outbox: FakeProcessor
    database: FakeDatabase


def _result(*, failed: int = 0) -> ProcessStorageOutboxResultDTO:
    return ProcessStorageOutboxResultDTO(
        events_seen=1,
        events_processed=1 - failed,
        events_deferred=0,
        events_failed=failed,
        metadata_objects_deleted=1,
        physical_objects_deleted=1 - failed,
    )


async def test_once_disposes_database_and_reports_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    processor = FakeProcessor(_result())
    container = FakeContainer(processor, FakeDatabase())
    settings = SimpleNamespace(
        outbox_worker_event_batch_size=32,
        outbox_orphan_sweep_batch_size=100,
        outbox_worker_poll_seconds=5,
    )
    heartbeats: list[Path] = []
    monkeypatch.setattr(process_storage_outbox, "load_settings", lambda: settings)
    monkeypatch.setattr(ApplicationContainer, "build", lambda settings: container)
    monkeypatch.setattr(
        process_storage_outbox,
        "_write_heartbeat",
        lambda path: heartbeats.append(path),
    )

    exit_code = await process_storage_outbox._run(
        once=True,
        poll_seconds=None,
        event_batch_size=None,
        orphan_batch_size=None,
    )

    assert exit_code == 0
    assert processor.commands == [
        ProcessStorageOutboxCommandDTO(event_batch_size=32, orphan_batch_size=100)
    ]
    assert container.database.disposed
    assert heartbeats == [process_storage_outbox._HEARTBEAT_PATH]
    output = capsys.readouterr().out
    assert '"component": "storage_outbox"' in output
    assert '"physical_objects_deleted": 1' in output


async def test_once_returns_nonzero_after_a_retryable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = FakeProcessor(_result(failed=1))
    container = FakeContainer(processor, FakeDatabase())
    settings = SimpleNamespace(
        outbox_worker_event_batch_size=1,
        outbox_orphan_sweep_batch_size=1,
        outbox_worker_poll_seconds=5,
    )
    monkeypatch.setattr(process_storage_outbox, "load_settings", lambda: settings)
    monkeypatch.setattr(ApplicationContainer, "build", lambda settings: container)

    exit_code = await process_storage_outbox._run(
        once=True,
        poll_seconds=1,
        event_batch_size=1,
        orphan_batch_size=1,
    )

    assert exit_code == 1
    assert container.database.disposed


def test_main_validates_bounds_and_passes_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[dict[str, int | bool | None]] = []

    async def fake_run(**kwargs: int | bool | None) -> int:
        received.append(kwargs)
        return 0

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "process_storage_outbox",
            "--once",
            "--poll-seconds",
            "2",
            "--event-batch-size",
            "3",
            "--orphan-batch-size",
            "4",
        ],
    )
    monkeypatch.setattr(process_storage_outbox, "_run", fake_run)

    with pytest.raises(SystemExit) as exited:
        process_storage_outbox.main()

    assert exited.value.code == 0
    assert received == [
        {
            "once": True,
            "poll_seconds": 2,
            "event_batch_size": 3,
            "orphan_batch_size": 4,
        }
    ]


@pytest.mark.parametrize("value", ["0", "not-an-int"])
def test_positive_int_rejects_invalid_cli_values(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["process_storage_outbox", "--poll-seconds", value],
    )
    with pytest.raises(SystemExit):
        process_storage_outbox.main()


def test_main_rejects_unbounded_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["process_storage_outbox", "--event-batch-size", "201"],
    )

    with pytest.raises(SystemExit):
        process_storage_outbox.main()


def test_heartbeat_creation_uses_the_configured_ephemeral_path(tmp_path: Path) -> None:
    heartbeat = tmp_path / "storage-outbox.heartbeat"

    process_storage_outbox._write_heartbeat(heartbeat)

    assert heartbeat.is_file()
