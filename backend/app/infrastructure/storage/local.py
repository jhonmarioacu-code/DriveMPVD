"""Local bounded-memory storage rooted under the configured data directory."""

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, cast
from uuid import UUID

from app.application.ports.file_storage import (
    ByteRangeDTO,
    PhysicalObjectDTO,
    StagedUploadDTO,
    StorageKey,
    StoredObjectDTO,
)
from app.infrastructure.exceptions import FileStorageError


class LocalFileStorageProvider:
    def __init__(
        self,
        root: Path,
        *,
        stream_block_size: int = 1024 * 1024,
        write_buffer_size: int | None = None,
    ) -> None:
        if stream_block_size <= 0:
            msg = "stream_block_size must be positive"
            raise ValueError(msg)
        if write_buffer_size is not None and write_buffer_size <= 0:
            msg = "write_buffer_size must be positive"
            raise ValueError(msg)
        self._root = root.resolve()
        self._staging = self._root / "staging"
        self._objects = self._root / "objects"
        self._lost_found = self._root / "lost+found"
        self._block_size = stream_block_size
        self._write_buffer_size = write_buffer_size or stream_block_size

    async def create_upload(self, upload_id: UUID) -> None:
        path = self._staging_path(upload_id)
        try:
            await asyncio.to_thread(self._staging.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(self._objects.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(self._create_empty, path)
            await asyncio.to_thread(self._fsync_directory, path.parent)
        except OSError as exc:
            raise FileStorageError() from exc

    async def append_chunk(
        self,
        upload_id: UUID,
        *,
        offset: int,
        chunks: AsyncIterator[bytes],
    ) -> int:
        path = self._staging_path(upload_id)
        handle = None
        try:
            handle = await asyncio.to_thread(path.open, "r+b", buffering=0)
            actual_size = await asyncio.to_thread(self._handle_size, handle)
            if actual_size != offset:
                raise FileStorageError("The staging offset is inconsistent.")
            await asyncio.to_thread(handle.seek, offset)
            async for chunk in _coalesce_chunks(
                chunks,
                maximum_size=self._write_buffer_size,
            ):
                await asyncio.to_thread(self._write_all, handle, chunk)
            await asyncio.to_thread(os.fsync, handle.fileno())
            return await asyncio.to_thread(self._handle_size, handle)
        except FileStorageError:
            if handle is not None:
                await asyncio.to_thread(self._truncate, handle, offset)
            raise
        except (OSError, ValueError) as exc:
            if handle is not None:
                await asyncio.to_thread(self._truncate, handle, offset)
            raise FileStorageError() from exc
        finally:
            if handle is not None:
                await asyncio.to_thread(handle.close)

    async def publish_upload(
        self,
        upload_id: UUID,
        *,
        expected_size: int,
    ) -> StoredObjectDTO:
        source = self._staging_path(upload_id)
        key = self._object_key(upload_id)
        destination = self._key_path(key)
        try:
            actual_size = await asyncio.to_thread(lambda: source.stat().st_size)
            if actual_size != expected_size:
                raise FileStorageError("The staged file size is inconsistent.")
            await asyncio.to_thread(
                destination.parent.mkdir, parents=True, exist_ok=True
            )
            if await asyncio.to_thread(destination.exists):
                raise FileStorageError("The destination object already exists.")
            await asyncio.to_thread(os.replace, source, destination)
            await asyncio.to_thread(self._fsync_directory, source.parent)
            await asyncio.to_thread(self._fsync_directory, destination.parent)
            return StoredObjectDTO(key=key, size=actual_size)
        except FileStorageError:
            raise
        except OSError as exc:
            raise FileStorageError() from exc

    def stream_upload(self, upload_id: UUID) -> AsyncIterator[bytes]:
        return self._stream_path(self._staging_path(upload_id))

    async def upload_size(self, upload_id: UUID) -> int:
        try:
            return await asyncio.to_thread(
                lambda: self._staging_path(upload_id).stat().st_size
            )
        except OSError as exc:
            raise FileStorageError() from exc

    async def discard_upload(self, upload_id: UUID) -> None:
        try:
            path = self._staging_path(upload_id)
            existed = await asyncio.to_thread(path.exists)
            await asyncio.to_thread(path.unlink, missing_ok=True)
            if existed:
                await asyncio.to_thread(self._fsync_directory, path.parent)
        except OSError as exc:
            raise FileStorageError() from exc

    async def truncate_upload(self, upload_id: UUID, *, offset: int) -> None:
        handle = None
        try:
            handle = await asyncio.to_thread(
                self._staging_path(upload_id).open,
                "r+b",
                buffering=0,
            )
            await asyncio.to_thread(self._truncate, handle, offset)
        except OSError as exc:
            raise FileStorageError() from exc
        finally:
            if handle is not None:
                await asyncio.to_thread(handle.close)

    def stream(
        self,
        key: StorageKey,
        *,
        byte_range: ByteRangeDTO | None = None,
    ) -> AsyncIterator[bytes]:
        return self._stream_path(self._key_path(key), byte_range=byte_range)

    async def stat(self, key: StorageKey) -> StoredObjectDTO | None:
        try:
            size = await asyncio.to_thread(lambda: self._key_path(key).stat().st_size)
            return StoredObjectDTO(key=key, size=size)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise FileStorageError() from exc

    async def delete(self, key: StorageKey) -> None:
        try:
            path = self._key_path(key)
            existed = await asyncio.to_thread(path.exists)
            await asyncio.to_thread(path.unlink, missing_ok=True)
            if existed:
                await asyncio.to_thread(self._fsync_directory, path.parent)
        except OSError as exc:
            raise FileStorageError() from exc

    async def list_objects(self) -> AsyncIterator[PhysicalObjectDTO]:
        async for path in self._walk_regular_files(self._objects):
            try:
                stat = await asyncio.to_thread(path.stat, follow_symlinks=False)
                relative = path.relative_to(self._root).as_posix()
            except (FileNotFoundError, OSError, ValueError):
                continue
            yield PhysicalObjectDTO(
                key=StorageKey(relative),
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )

    async def list_staged_uploads(self) -> AsyncIterator[StagedUploadDTO]:
        async for path in self._walk_regular_files(self._staging):
            if path.parent != self._staging or path.suffix != ".part":
                continue
            try:
                upload_id = UUID(path.stem)
                if path.name != f"{upload_id}.part":
                    continue
                stat = await asyncio.to_thread(path.stat, follow_symlinks=False)
            except (FileNotFoundError, OSError, ValueError):
                continue
            yield StagedUploadDTO(
                upload_id=upload_id,
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )

    async def quarantine(self, key: StorageKey) -> None:
        """Move an unknown object out of the live namespace without deleting it."""
        source = self._key_path(key)
        logical = PurePosixPath(str(key))
        destination = self._lost_found / Path(*logical.parts)
        try:
            if not await asyncio.to_thread(source.exists):
                return
            await asyncio.to_thread(
                destination.parent.mkdir,
                parents=True,
                exist_ok=True,
            )
            if await asyncio.to_thread(destination.exists):
                raise FileStorageError(
                    "The quarantine destination already exists; manual review is required."
                )
            await asyncio.to_thread(os.replace, source, destination)
            await asyncio.to_thread(self._fsync_directory, source.parent)
            await asyncio.to_thread(self._fsync_directory, destination.parent)
        except FileStorageError:
            raise
        except OSError as exc:
            raise FileStorageError() from exc

    async def _stream_path(
        self,
        path: Path,
        *,
        byte_range: ByteRangeDTO | None = None,
    ) -> AsyncIterator[bytes]:
        handle = None
        try:
            handle = await asyncio.to_thread(path.open, "rb", buffering=0)
            remaining: int | None = None
            if byte_range is not None:
                if byte_range.start < 0 or byte_range.end < byte_range.start:
                    raise FileStorageError("The byte range is invalid.")
                await asyncio.to_thread(handle.seek, byte_range.start)
                remaining = byte_range.end - byte_range.start + 1
            while remaining is None or remaining > 0:
                size = (
                    self._block_size
                    if remaining is None
                    else min(self._block_size, remaining)
                )
                chunk = await asyncio.to_thread(handle.read, size)
                if not chunk:
                    break
                if remaining is not None:
                    remaining -= len(chunk)
                yield chunk
        except FileStorageError:
            raise
        except OSError as exc:
            raise FileStorageError() from exc
        finally:
            if handle is not None:
                await asyncio.to_thread(handle.close)

    def _staging_path(self, upload_id: UUID) -> Path:
        return self._staging / f"{upload_id}.part"

    @staticmethod
    def _object_key(upload_id: UUID) -> StorageKey:
        hexadecimal = upload_id.hex
        return StorageKey(f"objects/{hexadecimal[:2]}/{hexadecimal[2:4]}/{upload_id}")

    def _key_path(self, key: StorageKey) -> Path:
        logical = PurePosixPath(str(key))
        if logical.is_absolute() or ".." in logical.parts:
            raise FileStorageError("The storage key is invalid.")
        candidate = (self._root / Path(*logical.parts)).resolve()
        if not candidate.is_relative_to(self._root):
            raise FileStorageError("The storage key escapes the configured root.")
        return candidate

    @staticmethod
    async def _walk_regular_files(root: Path) -> AsyncIterator[Path]:
        """Walk without following symlinks and without retaining the whole tree."""
        if not await asyncio.to_thread(root.is_dir):
            return
        pending = [root]
        while pending:
            directory = pending.pop()
            try:
                directories, files = await asyncio.to_thread(
                    LocalFileStorageProvider._directory_entries,
                    directory,
                )
            except OSError as exc:
                raise FileStorageError() from exc
            pending.extend(reversed(directories))
            for path in files:
                yield path

    @staticmethod
    def _directory_entries(directory: Path) -> tuple[list[Path], list[Path]]:
        directories: list[Path] = []
        files: list[Path] = []
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    directories.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    files.append(Path(entry.path))
        directories.sort(key=lambda path: path.name)
        files.sort(key=lambda path: path.name)
        return directories, files

    @staticmethod
    def _create_empty(path: Path) -> None:
        with path.open("xb"):
            pass

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        """Persist directory entries on POSIX; Windows has no directory fsync."""
        if os.name != "posix":
            return
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _handle_size(handle: object) -> int:
        return os.fstat(handle.fileno()).st_size  # type: ignore[attr-defined]

    @staticmethod
    def _write_all(handle: object, payload: bytes) -> None:
        """Persist a bounded payload even if the filesystem writes partially."""
        file_handle = cast(BinaryIO, handle)
        view = memoryview(payload)
        while view:
            written = file_handle.write(view)
            if written <= 0:
                msg = "The staging write did not make progress."
                raise OSError(msg)
            view = view[written:]

    @staticmethod
    def _truncate(handle: object, offset: int) -> None:
        handle.truncate(offset)  # type: ignore[attr-defined]
        os.fsync(handle.fileno())  # type: ignore[attr-defined]


async def _coalesce_chunks(
    chunks: AsyncIterator[bytes],
    *,
    maximum_size: int,
) -> AsyncIterator[bytes]:
    """Coalesce small ASGI fragments without retaining a complete upload."""
    pending = bytearray()
    async for chunk in chunks:
        if not chunk:
            continue
        if not pending and len(chunk) >= maximum_size:
            yield chunk
            continue
        position = 0
        while position < len(chunk):
            remaining_capacity = maximum_size - len(pending)
            next_position = min(position + remaining_capacity, len(chunk))
            pending.extend(chunk[position:next_position])
            position = next_position
            if len(pending) == maximum_size:
                yield bytes(pending)
                pending.clear()
    if pending:
        yield bytes(pending)
