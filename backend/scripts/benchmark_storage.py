"""Measure bounded-memory local storage throughput with a disposable fixture.

The default is intentionally small. A 50 GiB run requires --allow-large and
enough free space on the selected filesystem, so it cannot be started by
accident from a developer shell or CI job.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
import tracemalloc
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast
from uuid import uuid4

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.infrastructure.storage.local import LocalFileStorageProvider

_MEBIBYTE = 1024 * 1024
_GIBIBYTE = 1024 * _MEBIBYTE
_DEFAULT_SIZE_BYTES = 128 * _MEBIBYTE
_LARGE_RUN_THRESHOLD_BYTES = _GIBIBYTE


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark local resumable upload and download streaming."
    )
    size = parser.add_mutually_exclusive_group()
    size.add_argument(
        "--size-mib",
        type=int,
        default=128,
        help="Fixture size in MiB (default: 128).",
    )
    size.add_argument(
        "--size-gib",
        type=int,
        help="Fixture size in GiB; requires --allow-large when above 1 GiB.",
    )
    parser.add_argument(
        "--source-chunk-kib",
        type=int,
        default=64,
        help="Incoming ASGI-equivalent fragment size in KiB (default: 64).",
    )
    parser.add_argument(
        "--stream-block-kib",
        type=int,
        default=1024,
        help="Storage read block size in KiB (default: 1024).",
    )
    parser.add_argument(
        "--write-buffer-kib",
        type=int,
        default=1024,
        help="Bounded write coalescing buffer in KiB (default: 1024).",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        help=(
            "Existing directory on the filesystem to measure "
            "(defaults to system temp)."
        ),
    )
    parser.add_argument(
        "--allow-large",
        action="store_true",
        help="Required for a fixture larger than 1 GiB.",
    )
    return parser.parse_args()


def _size_bytes(arguments: argparse.Namespace) -> int:
    size_gib = cast(int | None, arguments.size_gib)
    if size_gib is not None:
        return size_gib * _GIBIBYTE
    return cast(int, arguments.size_mib) * _MEBIBYTE


def _validate(arguments: argparse.Namespace, size_bytes: int) -> Path:
    if size_bytes <= 0:
        raise ValueError("The fixture size must be positive.")
    if any(
        value <= 0
        for value in (
            arguments.source_chunk_kib,
            arguments.stream_block_kib,
            arguments.write_buffer_kib,
        )
    ):
        raise ValueError("Chunk and buffer sizes must be positive.")
    if size_bytes > _LARGE_RUN_THRESHOLD_BYTES and not arguments.allow_large:
        raise ValueError("Fixtures larger than 1 GiB require --allow-large.")
    directory = (arguments.directory or Path(tempfile.gettempdir())).resolve()
    if not directory.is_dir():
        raise ValueError(f"Benchmark directory does not exist: {directory}")
    free_bytes = shutil.disk_usage(directory).free
    reserve_bytes = max(_GIBIBYTE, size_bytes // 10)
    if free_bytes < size_bytes + reserve_bytes:
        raise ValueError(
            "Insufficient free disk space for fixture plus a 10%/1 GiB reserve."
        )
    return directory


async def _generated_chunks(
    *,
    total_size: int,
    source_chunk_size: int,
) -> AsyncIterator[bytes]:
    block = b"\0" * source_chunk_size
    remaining = total_size
    while remaining:
        next_size = min(source_chunk_size, remaining)
        yield block if next_size == source_chunk_size else block[:next_size]
        remaining -= next_size


def _rate(bytes_count: int, duration_seconds: float) -> float:
    return bytes_count / duration_seconds if duration_seconds > 0 else 0.0


async def _run(
    arguments: argparse.Namespace,
    size_bytes: int,
    directory: Path,
) -> dict[str, object]:
    source_chunk_size = arguments.source_chunk_kib * 1024
    stream_block_size = arguments.stream_block_kib * 1024
    write_buffer_size = arguments.write_buffer_kib * 1024
    with tempfile.TemporaryDirectory(
        prefix="drivempvd-storage-benchmark-",
        dir=directory,
    ) as temporary:
        provider = LocalFileStorageProvider(
            Path(temporary),
            stream_block_size=stream_block_size,
            write_buffer_size=write_buffer_size,
        )
        upload_id = uuid4()
        await provider.create_upload(upload_id)
        tracemalloc.start()

        started = time.perf_counter()
        appended = await provider.append_chunk(
            upload_id,
            offset=0,
            chunks=_generated_chunks(
                total_size=size_bytes,
                source_chunk_size=source_chunk_size,
            ),
        )
        append_seconds = time.perf_counter() - started

        started = time.perf_counter()
        stored = await provider.publish_upload(upload_id, expected_size=size_bytes)
        publish_seconds = time.perf_counter() - started

        streamed = 0
        started = time.perf_counter()
        async for chunk in provider.stream(stored.key):
            streamed += len(chunk)
        stream_seconds = time.perf_counter() - started

        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if appended != size_bytes or streamed != size_bytes:
            msg = "The benchmark did not transfer the expected byte count."
            raise RuntimeError(msg)
    return {
        "size_bytes": size_bytes,
        "source_chunk_bytes": source_chunk_size,
        "stream_block_bytes": stream_block_size,
        "write_buffer_bytes": write_buffer_size,
        "append_seconds": round(append_seconds, 6),
        "append_mib_per_second": round(
            _rate(size_bytes, append_seconds) / _MEBIBYTE,
            2,
        ),
        "publish_seconds": round(publish_seconds, 6),
        "stream_seconds": round(stream_seconds, 6),
        "stream_mib_per_second": round(
            _rate(size_bytes, stream_seconds) / _MEBIBYTE,
            2,
        ),
        "tracemalloc_peak_bytes": peak,
    }


def main() -> None:
    arguments = _parse_arguments()
    try:
        size_bytes = _size_bytes(arguments)
        directory = _validate(arguments, size_bytes)
    except ValueError as exc:
        raise SystemExit(f"benchmark configuration error: {exc}") from exc
    result = asyncio.run(_run(arguments, size_bytes, directory))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
