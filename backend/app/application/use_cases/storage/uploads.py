"""Resumable bounded-memory upload orchestration."""

import hashlib
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from uuid import UUID

from app.application.dtos.storage import (
    AppendUploadChunkCommandDTO,
    CancelUploadCommandDTO,
    CompleteUploadCommandDTO,
    StartUploadCommandDTO,
    StorageEntryDTO,
    UploadChunkResultDTO,
    UploadPolicyDTO,
    UploadSessionDTO,
)
from app.application.exceptions import (
    StorageEntryNotFoundError,
    StorageNameConflictError,
    UploadOffsetMismatchError,
    UploadSessionNotFoundError,
    UploadStateConflictError,
    UploadValidationError,
)
from app.application.ports.auth_services import Clock
from app.application.ports.file_storage import FileStorageProvider, StorageKey
from app.application.ports.identifiers import IdGenerator
from app.application.ports.media_processing import VirusScanner
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.ports.upload_services import (
    MimeDetector,
    UploadMetricDTO,
    UploadMetricsRecorder,
)
from app.application.use_cases.storage.mappers import entry_to_dto
from app.domain.storage.entities import File, FileVersion, StorageObject, UploadSession
from app.domain.storage.enums import StorageObjectStatus, UploadStatus
from app.domain.storage.value_objects import EntryName, Sha256Checksum

_INSPECTION_PREFIX_SIZE = 64 * 1024


class UploadUseCase:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        storage: FileStorageProvider,
        id_generator: IdGenerator,
        clock: Clock,
        mime_detector: MimeDetector,
        metrics: UploadMetricsRecorder,
        policy: UploadPolicyDTO,
        virus_scanner: VirusScanner | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._storage = storage
        self._id_generator = id_generator
        self._clock = clock
        self._mime_detector = mime_detector
        self._metrics = metrics
        self._policy = policy
        self._virus_scanner = virus_scanner

    def _record_metric(
        self,
        *,
        operation: str,
        started_at: datetime,
        size: int,
        error: Exception | None = None,
    ) -> None:
        duration = max(0.0, (self._clock.now() - started_at).total_seconds())
        self._metrics.record(
            UploadMetricDTO(
                operation=operation,
                outcome="error" if error is not None else "success",
                duration_seconds=duration,
                size_bytes=size,
                average_bytes_per_second=size / duration if duration > 0 else 0.0,
                error_code=(
                    str(getattr(error, "code", type(error).__name__))
                    if error is not None
                    else None
                ),
            )
        )

    @staticmethod
    def _require_upload(
        upload: UploadSession | None,
        owner_id: UUID,
    ) -> UploadSession:
        if upload is None or upload.owner_id != owner_id:
            raise UploadSessionNotFoundError()
        return upload


class StartUploadUseCase(UploadUseCase):
    async def execute(self, command: StartUploadCommandDTO) -> UploadSessionDTO:
        started_at = self._clock.now()
        upload_id: UUID | None = None
        try:
            name = EntryName.create(command.filename)
            extension = name.extension
            declared_mime = _canonical_mime(command.declared_mime_type)
            _validate_start_policy(
                command.expected_size, extension, declared_mime, self._policy
            )
            now = self._clock.now()
            async with self._unit_of_work_factory() as unit_of_work:
                folder = await unit_of_work.storage.get_folder(
                    command.parent_id,
                    for_update=True,
                )
                if folder is None or folder.owner_id != command.owner_id:
                    raise StorageEntryNotFoundError()
                path_length = await unit_of_work.storage.logical_path_length(folder.id)
                if (
                    path_length + len(name.value)
                    > self._policy.maximum_logical_path_length
                ):
                    raise UploadValidationError("The logical path is too long.")
                if await unit_of_work.storage.name_exists(
                    parent_id=folder.id,
                    normalized_name=name.normalized,
                ):
                    raise StorageNameConflictError()
                upload_id = self._id_generator.new()
                internal_name = (
                    f"{upload_id}.{extension}" if extension else str(upload_id)
                )
                session = UploadSession(
                    id=upload_id,
                    owner_id=command.owner_id,
                    parent_id=folder.id,
                    original_name=name.value,
                    internal_name=internal_name,
                    expected_size=command.expected_size,
                    uploaded_bytes=0,
                    mime_type=declared_mime,
                    extension=extension,
                    checksum_sha256=None,
                    staging_key=str(upload_id),
                    status=UploadStatus.CREATED,
                    expires_at=now
                    + timedelta(seconds=self._policy.session_ttl_seconds),
                    created_at=now,
                    updated_at=now,
                )
                await self._storage.create_upload(upload_id)
                await unit_of_work.storage.add_upload_session(session)
                await unit_of_work.commit()
            self._record_metric(operation="start", started_at=started_at, size=0)
            return _upload_dto(session)
        except Exception as exc:
            if upload_id is not None:
                await self._storage.discard_upload(upload_id)
            self._record_metric(
                operation="start", started_at=started_at, size=0, error=exc
            )
            raise


class GetUploadStatusUseCase(UploadUseCase):
    async def execute(self, *, owner_id: UUID, upload_id: UUID) -> UploadSessionDTO:
        async with self._unit_of_work_factory() as unit_of_work:
            upload = self._require_upload(
                await unit_of_work.storage.get_upload_session(upload_id),
                owner_id,
            )
        return _upload_dto(upload)


class AppendUploadChunkUseCase(UploadUseCase):
    async def execute(
        self,
        command: AppendUploadChunkCommandDTO,
    ) -> UploadChunkResultDTO:
        started_at = self._clock.now()
        stream = _BoundedHashingStream(command.chunks, self._policy.maximum_chunk_size)
        previous_offset: int | None = None
        append_completed = False
        committed = False
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                upload = self._require_upload(
                    await unit_of_work.storage.get_upload_session(
                        command.upload_id,
                        for_update=True,
                    ),
                    command.owner_id,
                )
                _require_writable(upload, self._clock.now())
                if command.offset != upload.uploaded_bytes:
                    raise UploadOffsetMismatchError(
                        expected_offset=upload.uploaded_bytes
                    )
                previous_offset = upload.uploaded_bytes
                stream.set_remaining(upload.expected_size - upload.uploaded_bytes)
                persisted_offset = await self._storage.append_chunk(
                    upload.id,
                    offset=upload.uploaded_bytes,
                    chunks=stream,
                )
                append_completed = True
                if stream.size == 0:
                    raise UploadValidationError("A chunk cannot be empty.")
                if persisted_offset != upload.uploaded_bytes + stream.size:
                    raise UploadValidationError(
                        "The persisted chunk length is inconsistent."
                    )
                upload.record_progress(
                    persisted_offset=persisted_offset,
                    now=self._clock.now(),
                )
                await unit_of_work.storage.save_upload_session(upload)
                await unit_of_work.commit()
                committed = True
            self._record_metric(
                operation="chunk",
                started_at=started_at,
                size=stream.size,
            )
            return UploadChunkResultDTO(
                upload_id=upload.id,
                offset=persisted_offset,
                received_bytes=stream.size,
                chunk_sha256=stream.hexdigest,
            )
        except Exception as exc:
            if append_completed and not committed and previous_offset is not None:
                await self._storage.truncate_upload(
                    command.upload_id,
                    offset=previous_offset,
                )
            self._record_metric(
                operation="chunk",
                started_at=started_at,
                size=stream.size,
                error=exc,
            )
            raise


class CompleteUploadUseCase(UploadUseCase):
    async def execute(self, command: CompleteUploadCommandDTO) -> StorageEntryDTO:
        started_at = self._clock.now()
        published_key: StorageKey | None = None
        inspected_size = 0
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                upload = self._require_upload(
                    await unit_of_work.storage.get_upload_session(
                        command.upload_id,
                        for_update=True,
                    ),
                    command.owner_id,
                )
                _require_writable(upload, self._clock.now())
                if upload.uploaded_bytes != upload.expected_size:
                    raise UploadStateConflictError("The upload is incomplete.")
                checksum, inspected_size, prefix = await _inspect_stream(
                    self._storage.stream_upload(upload.id)
                )
                actual_size = await self._storage.upload_size(upload.id)
                if (
                    inspected_size != upload.expected_size
                    or actual_size != inspected_size
                ):
                    raise UploadValidationError(
                        "The uploaded file size is inconsistent."
                    )
                detected_mime = self._mime_detector.detect(
                    prefix,
                    filename=upload.original_name,
                )
                _validate_mime(upload.mime_type, detected_mime, self._policy)
                if self._virus_scanner is not None:
                    scan = await self._virus_scanner.scan(
                        self._storage.stream_upload(upload.id)
                    )
                    if not scan.clean:
                        raise UploadValidationError(
                            "The uploaded content was rejected."
                        )
                # Lock the parent folder so that concurrent completions with the
                # same filename cannot both pass the name_exists() check before
                # either transaction commits. This mirrors the lock acquired by
                # StartUploadUseCase and ensures the database unique constraint
                # is the last line of defence, not the first.
                parent = await unit_of_work.storage.get_folder(
                    upload.parent_id,
                    for_update=True,
                )
                if parent is None or parent.owner_id != upload.owner_id:
                    raise StorageEntryNotFoundError()
                if await unit_of_work.storage.name_exists(
                    parent_id=upload.parent_id,
                    normalized_name=EntryName.create(upload.original_name).normalized,
                ):
                    raise StorageNameConflictError()
                stored = await self._storage.publish_upload(
                    upload.id,
                    expected_size=inspected_size,
                )
                published_key = stored.key
                now = self._clock.now()
                file_id = self._id_generator.new()
                object_id = self._id_generator.new()
                storage_object = StorageObject(
                    id=object_id,
                    storage_key=str(stored.key),
                    size=stored.size,
                    mime_type=detected_mime,
                    checksum_sha256=checksum,
                    status=StorageObjectStatus.READY,
                    created_at=now,
                    updated_at=now,
                )
                name = EntryName.create(upload.original_name)
                file = File(
                    id=file_id,
                    owner_id=upload.owner_id,
                    parent_id=upload.parent_id,
                    name=name.value,
                    normalized_name=name.normalized,
                    original_name=upload.original_name,
                    internal_name=upload.internal_name,
                    size=stored.size,
                    mime_type=detected_mime,
                    extension=upload.extension,
                    checksum_sha256=checksum,
                    current_version_number=1,
                    created_at=now,
                    updated_at=now,
                )
                version = FileVersion(
                    id=self._id_generator.new(),
                    file_id=file.id,
                    storage_object_id=storage_object.id,
                    version_number=1,
                    original_name=file.original_name,
                    size=file.size,
                    mime_type=file.mime_type,
                    extension=file.extension,
                    checksum_sha256=file.checksum_sha256,
                    created_by=file.owner_id,
                    created_at=now,
                )
                upload.complete(checksum=Sha256Checksum.create(checksum), now=now)
                await unit_of_work.storage.add_storage_object(storage_object)
                await unit_of_work.storage.add_file(file, version)
                await unit_of_work.storage.save_upload_session(upload)
                await unit_of_work.commit()
            self._record_metric(
                operation="complete",
                started_at=started_at,
                size=inspected_size,
            )
            return entry_to_dto(file)
        except Exception as exc:
            if published_key is not None:
                await self._storage.delete(published_key)
            self._record_metric(
                operation="complete",
                started_at=started_at,
                size=inspected_size,
                error=exc,
            )
            raise


class CancelUploadUseCase(UploadUseCase):
    async def execute(self, command: CancelUploadCommandDTO) -> UploadSessionDTO:
        started_at = self._clock.now()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                upload = self._require_upload(
                    await unit_of_work.storage.get_upload_session(
                        command.upload_id,
                        for_update=True,
                    ),
                    command.owner_id,
                )
                if upload.status is UploadStatus.COMPLETED:
                    raise UploadStateConflictError()
                upload.status = UploadStatus.CANCELLED
                upload.updated_at = self._clock.now()
                await unit_of_work.storage.save_upload_session(upload)
                await unit_of_work.commit()
            await self._storage.discard_upload(upload.id)
            self._record_metric(operation="cancel", started_at=started_at, size=0)
            return _upload_dto(upload)
        except Exception as exc:
            self._record_metric(
                operation="cancel", started_at=started_at, size=0, error=exc
            )
            raise


class _BoundedHashingStream:
    def __init__(self, source: AsyncIterator[bytes], maximum_size: int) -> None:
        self._source = source
        self._maximum_size = maximum_size
        self._remaining: int | None = None
        self._hasher = hashlib.sha256()
        self.size = 0

    def set_remaining(self, remaining: int) -> None:
        self._remaining = remaining

    def __aiter__(self) -> "_BoundedHashingStream":
        return self

    async def __anext__(self) -> bytes:
        chunk = await anext(self._source)
        next_size = self.size + len(chunk)
        if next_size > self._maximum_size:
            raise UploadValidationError(
                "The chunk exceeds the configured maximum size."
            )
        if self._remaining is not None and next_size > self._remaining:
            raise UploadValidationError("The chunk exceeds the declared file size.")
        self._hasher.update(chunk)
        self.size = next_size
        return chunk

    @property
    def hexdigest(self) -> str:
        return self._hasher.hexdigest()


async def _inspect_stream(chunks: AsyncIterator[bytes]) -> tuple[str, int, bytes]:
    hasher = hashlib.sha256()
    size = 0
    prefix = bytearray()
    async for chunk in chunks:
        hasher.update(chunk)
        size += len(chunk)
        if len(prefix) < _INSPECTION_PREFIX_SIZE:
            prefix.extend(chunk[: _INSPECTION_PREFIX_SIZE - len(prefix)])
    return hasher.hexdigest(), size, bytes(prefix)


def _canonical_mime(value: str) -> str:
    mime_type = value.partition(";")[0].strip().casefold()
    if "/" not in mime_type or len(mime_type) > 255:
        raise UploadValidationError("The declared MIME type is invalid.")
    return mime_type


def _validate_start_policy(
    size: int,
    extension: str,
    mime_type: str,
    policy: UploadPolicyDTO,
) -> None:
    if size < 0 or size > policy.maximum_file_size:
        raise UploadValidationError("The declared file size is not allowed.")
    if extension in policy.blocked_extensions:
        raise UploadValidationError("The file extension is blocked.")
    if policy.allowed_extensions and extension not in policy.allowed_extensions:
        raise UploadValidationError("The file extension is not allowed.")
    if policy.allowed_mime_types and mime_type not in policy.allowed_mime_types:
        raise UploadValidationError("The declared MIME type is not allowed.")


def _validate_mime(
    declared: str | None,
    detected: str,
    policy: UploadPolicyDTO,
) -> None:
    if policy.allowed_mime_types and detected not in policy.allowed_mime_types:
        raise UploadValidationError("The detected MIME type is not allowed.")
    if declared in {None, "application/octet-stream"}:
        return
    compatible_containers = {
        "application/zip": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
    }
    if declared != detected and declared not in compatible_containers.get(
        detected, set()
    ):
        raise UploadValidationError("Declared and detected MIME types do not match.")


def _require_writable(upload: UploadSession, now: datetime) -> None:
    if upload.expires_at <= now:
        raise UploadStateConflictError("The upload session has expired.")
    if upload.status not in {UploadStatus.CREATED, UploadStatus.UPLOADING}:
        raise UploadStateConflictError()


def _upload_dto(upload: UploadSession) -> UploadSessionDTO:
    return UploadSessionDTO(
        id=upload.id,
        parent_id=upload.parent_id,
        filename=upload.original_name,
        expected_size=upload.expected_size,
        uploaded_bytes=upload.uploaded_bytes,
        declared_mime_type=upload.mime_type,
        extension=upload.extension,
        status=upload.status.value,
        expires_at=upload.expires_at,
        checksum_sha256=upload.checksum_sha256,
    )
