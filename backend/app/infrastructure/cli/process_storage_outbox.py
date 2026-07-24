"""Run the bounded, retry-safe storage outbox consumer."""

import argparse
import asyncio
import json
from pathlib import Path
from tempfile import gettempdir

from app.application.dtos.outbox import (
    ProcessStorageOutboxCommandDTO,
    ProcessStorageOutboxResultDTO,
)
from app.infrastructure.config import load_settings
from app.infrastructure.container import ApplicationContainer

_HEARTBEAT_PATH = Path(gettempdir()) / "drivempvd-storage-outbox.heartbeat"


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _result_payload(result: ProcessStorageOutboxResultDTO) -> dict[str, int | str]:
    return {
        "component": "storage_outbox",
        "events_seen": result.events_seen,
        "events_processed": result.events_processed,
        "events_deferred": result.events_deferred,
        "events_failed": result.events_failed,
        "metadata_objects_deleted": result.metadata_objects_deleted,
        "physical_objects_deleted": result.physical_objects_deleted,
    }


async def _run(
    *,
    once: bool,
    poll_seconds: int | None,
    event_batch_size: int | None,
    orphan_batch_size: int | None,
) -> int:
    settings = load_settings()
    container = ApplicationContainer.build(settings)
    try:
        command = ProcessStorageOutboxCommandDTO(
            event_batch_size=(
                event_batch_size
                if event_batch_size is not None
                else settings.outbox_worker_event_batch_size
            ),
            orphan_batch_size=(
                orphan_batch_size
                if orphan_batch_size is not None
                else settings.outbox_orphan_sweep_batch_size
            ),
        )
        effective_poll_seconds = (
            poll_seconds
            if poll_seconds is not None
            else settings.outbox_worker_poll_seconds
        )
        while True:
            result = await container.process_storage_outbox.execute(command)
            await asyncio.to_thread(_write_heartbeat, _HEARTBEAT_PATH)
            if once or result.events_seen:
                print(json.dumps(_result_payload(result), sort_keys=True), flush=True)
            if once:
                return int(result.events_failed > 0)
            await asyncio.sleep(effective_poll_seconds)
    finally:
        await container.database.dispose()


def _write_heartbeat(path: Path) -> None:
    """Publish liveness only after a complete polling cycle returns."""
    path.touch(exist_ok=True)


def main() -> None:
    """Start one polling worker; --once is suitable for controlled validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="process one bounded polling cycle and exit",
    )
    parser.add_argument("--poll-seconds", type=_positive_int)
    parser.add_argument("--event-batch-size", type=_positive_int)
    parser.add_argument("--orphan-batch-size", type=_positive_int)
    args = parser.parse_args()
    if args.event_batch_size is not None and args.event_batch_size > 200:
        parser.error("--event-batch-size must be at most 200")
    if args.orphan_batch_size is not None and args.orphan_batch_size > 1_000:
        parser.error("--orphan-batch-size must be at most 1000")
    raise SystemExit(
        asyncio.run(
            _run(
                once=args.once,
                poll_seconds=args.poll_seconds,
                event_batch_size=args.event_batch_size,
                orphan_batch_size=args.orphan_batch_size,
            )
        )
    )


if __name__ == "__main__":
    main()
