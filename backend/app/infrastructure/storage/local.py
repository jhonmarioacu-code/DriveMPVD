"""Local bounded-memory storage rooted under the configured data directory."""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath
from uuid import UUID

from app.application.ports.file_storage import (
    ByteRangeDTO,
    StorageKey,
    StoredObjectDTO,
)
from app.infrastructure.exceptions import FileStorageError


class LocalFileStorageProvider:
    def __init__(self, root: Path, *, stream_block_size: int = 1024 * 1024) -> None:
        self._root = root.resolve()
        self._staging = self._root / "staging"
        self._objects = self._root / "objects"
        self._block_size = stream_block_size

    async def create_upload(self, upload_id: UUID) -> None:
        path = self._staging_path(upload_id)
        try:
            await asyncio.to_thread(self._staging.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(self._objects.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(self._create_empty, path)
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
            async for chunk in chunks:
                if chunk:
                    await asyncio.to_thread(handle.write, chunk)
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
            await asyncio.to_thread(
                self._staging_path(upload_id).unlink, missing_ok=True
            )
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
            await asyncio.to_thread(self._key_path(key).unlink, missing_ok=True)
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
    def _create_empty(path: Path) -> None:
        with path.open("xb"):
            pass

    @staticmethod
    def _handle_size(handle: object) -> int:
        return os.fstat(handle.fileno()).st_size  # type: ignore[attr-defined]

    @staticmethod
    def _truncate(handle: object, offset: int) -> None:
        handle.truncate(offset)  # type: ignore[attr-defined]
        os.fsync(handle.fileno())  # type: ignore[attr-defined]
