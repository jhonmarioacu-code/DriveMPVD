"""HTTP adapter for storage metadata commands and queries."""

from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.application.dtos.storage import (
    AppendUploadChunkCommandDTO,
    CancelUploadCommandDTO,
    CompleteUploadCommandDTO,
    CopyEntryCommandDTO,
    CreateFolderCommandDTO,
    FileDetailsDTO,
    ListFolderEntriesQueryDTO,
    MoveEntryCommandDTO,
    PermanentlyDeleteCommandDTO,
    RenameEntryCommandDTO,
    RestoreEntryCommandDTO,
    StartUploadCommandDTO,
    StorageEntryDTO,
    StorageListFiltersDTO,
    TrashEntryCommandDTO,
    TrashItemDTO,
    UploadChunkResultDTO,
    UploadSessionDTO,
)
from app.application.ports.download_services import (
    DownloadDeliveryProvider,
    DownloadMetricsRecorder,
)
from app.application.ports.file_storage import FileStorageProvider
from app.application.use_cases.storage import (
    AppendUploadChunkUseCase,
    CancelUploadUseCase,
    CompleteUploadUseCase,
    CopyEntryUseCase,
    CreateFolderUseCase,
    GetFileDetailsUseCase,
    GetFolderNavigationUseCase,
    GetUploadStatusUseCase,
    ListFolderEntriesUseCase,
    MoveEntryUseCase,
    PermanentlyDeleteUseCase,
    PrepareFileDownloadUseCase,
    RenameEntryUseCase,
    RestoreEntryUseCase,
    StartUploadUseCase,
    TrashEntryUseCase,
)
from app.presentation.auth import require_principal
from app.presentation.file_delivery import (
    RangeRequestError,
    base_download_headers,
    evaluate_preconditions,
    file_etag,
    is_inline_media_type,
    multipart_boundary,
    multipart_length,
    parse_ranges,
    stream_download,
)
from app.presentation.http_cache import (
    apply_cache_headers,
    conditional_not_modified,
    metadata_etag,
)
from app.presentation.schemas.envelope import (
    ApiError,
    ApiResponse,
    ErrorResponse,
    error_response,
    success_response,
)
from app.presentation.schemas.storage import (
    CopyEntryInput,
    CreateFolderInput,
    FileDetailsData,
    FolderBreadcrumbData,
    FolderEntriesData,
    FolderEntriesQuery,
    FolderNavigationData,
    MoveEntryInput,
    PermanentDeleteData,
    RenameEntryInput,
    RestoreTrashInput,
    StartUploadInput,
    StorageEntryData,
    TrashItemData,
    UploadChunkData,
    UploadSessionData,
)

_AUTH_SECURITY: list[dict[str, list[str]]] = [
    {"BearerAuth": []},
    {"AccessCookie": []},
]
_PROTECTED_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "CSRF validation failed."},
    404: {"model": ErrorResponse, "description": "The resource was not found."},
    409: {"model": ErrorResponse, "description": "The operation conflicts."},
    422: {"model": ErrorResponse, "description": "The request is invalid."},
}


@dataclass(frozen=True, slots=True)
class StorageRouteUseCases:
    get_navigation: GetFolderNavigationUseCase
    list_entries: ListFolderEntriesUseCase
    get_file: GetFileDetailsUseCase
    create_folder: CreateFolderUseCase
    rename_entry: RenameEntryUseCase
    move_entry: MoveEntryUseCase
    copy_entry: CopyEntryUseCase
    trash_entry: TrashEntryUseCase
    restore_entry: RestoreEntryUseCase
    permanently_delete: PermanentlyDeleteUseCase
    start_upload: StartUploadUseCase
    get_upload_status: GetUploadStatusUseCase
    append_upload_chunk: AppendUploadChunkUseCase
    complete_upload: CompleteUploadUseCase
    cancel_upload: CancelUploadUseCase
    prepare_download: PrepareFileDownloadUseCase
    file_storage: FileStorageProvider
    download_delivery: DownloadDeliveryProvider
    download_metrics: DownloadMetricsRecorder


def create_storage_router(
    use_cases: StorageRouteUseCases,
    *,
    csrf_header_name: str,
) -> APIRouter:
    router = APIRouter(prefix="/storage")

    @router.get(
        "/navigation",
        response_model=ApiResponse[FolderNavigationData],
        responses=_PROTECTED_RESPONSES,
        summary="Resolve the storage root or a folder breadcrumb path",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def get_folder_navigation(
        request: Request,
        folder_id: Annotated[UUID | None, Query()] = None,
    ) -> ApiResponse[FolderNavigationData]:
        principal = require_principal(request)
        path = await use_cases.get_navigation.execute(
            owner_id=principal.admin_id,
            folder_id=folder_id,
        )
        folder = path[-1]
        return success_response(
            FolderNavigationData(
                folder=_entry_data(folder),
                breadcrumbs=tuple(
                    FolderBreadcrumbData(id=item.id, name=item.name) for item in path
                ),
            ),
            request_id=request.state.request_id,
        )

    @router.get(
        "/folders/{folder_id}/entries",
        response_model=ApiResponse[FolderEntriesData],
        responses={
            **_PROTECTED_RESPONSES,
            304: {"description": "The cached representation is current."},
        },
        summary="List a folder's entries",
        description=(
            "Keyset-paginate direct children with sorting and metadata filters."
        ),
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def list_folder_entries(
        folder_id: UUID,
        query: Annotated[FolderEntriesQuery, Query()],
        request: Request,
        response: Response,
    ) -> Response | ApiResponse[FolderEntriesData]:
        principal = require_principal(request)
        page = await use_cases.list_entries.execute(
            ListFolderEntriesQueryDTO(
                owner_id=principal.admin_id,
                folder_id=folder_id,
                limit=query.limit,
                cursor=query.cursor,
                sort_by=query.sort_by,
                direction=query.direction,
                filters=StorageListFiltersDTO(
                    name_contains=query.name,
                    kind=query.kind,
                    extension=query.extension,
                    minimum_size=query.minimum_size,
                    maximum_size=query.maximum_size,
                    modified_from=query.modified_from,
                    modified_to=query.modified_to,
                ),
            )
        )
        data = FolderEntriesData(
            folder_id=folder_id,
            items=tuple(_entry_data(item) for item in page.items),
        )
        last_modified = max(
            (item.updated_at for item in page.items),
            default=None,
        )
        etag = metadata_etag(
            (
                str(folder_id),
                *(f"{item.id}:{item.updated_at.isoformat()}" for item in page.items),
                page.next_cursor or "",
            )
        )
        cached = conditional_not_modified(
            request,
            etag=etag,
            last_modified=last_modified,
        )
        if cached is not None:
            return cached
        apply_cache_headers(response, etag=etag, last_modified=last_modified)
        return success_response(
            data,
            request_id=request.state.request_id,
            next_cursor=page.next_cursor,
        )

    @router.get(
        "/files/{file_id}",
        response_model=ApiResponse[FileDetailsData],
        responses={
            **_PROTECTED_RESPONSES,
            304: {"description": "The cached representation is current."},
        },
        summary="Get file metadata",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def get_file(
        file_id: UUID,
        request: Request,
        response: Response,
    ) -> Response | ApiResponse[FileDetailsData]:
        principal = require_principal(request)
        result = await use_cases.get_file.execute(
            owner_id=principal.admin_id,
            file_id=file_id,
        )
        etag = metadata_etag(
            (
                str(result.id),
                str(result.current_version_number),
                result.updated_at.isoformat(),
                result.checksum_sha256,
            )
        )
        cached = conditional_not_modified(
            request,
            etag=etag,
            last_modified=result.updated_at,
        )
        if cached is not None:
            return cached
        apply_cache_headers(response, etag=etag, last_modified=result.updated_at)
        return success_response(
            _file_data(result),
            request_id=request.state.request_id,
        )

    @router.post(
        "/folders",
        response_model=ApiResponse[StorageEntryData],
        status_code=status.HTTP_201_CREATED,
        responses=_PROTECTED_RESPONSES,
        summary="Create a folder",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def create_folder(
        payload: CreateFolderInput,
        request: Request,
        response: Response,
    ) -> ApiResponse[StorageEntryData]:
        principal = require_principal(request)
        result = await use_cases.create_folder.execute(
            CreateFolderCommandDTO(principal.admin_id, payload.parent_id, payload.name)
        )
        response.headers["Location"] = str(
            request.url_for("list_folder_entries", folder_id=result.id)
        )
        return success_response(
            _entry_data(result),
            request_id=request.state.request_id,
        )

    @router.patch(
        "/entries/{entry_id}",
        response_model=ApiResponse[StorageEntryData],
        responses=_PROTECTED_RESPONSES,
        summary="Rename a storage entry",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def rename_entry(
        entry_id: UUID,
        payload: RenameEntryInput,
        request: Request,
    ) -> ApiResponse[StorageEntryData]:
        principal = require_principal(request)
        result = await use_cases.rename_entry.execute(
            RenameEntryCommandDTO(principal.admin_id, entry_id, payload.name)
        )
        return success_response(
            _entry_data(result), request_id=request.state.request_id
        )

    @router.post(
        "/entries/{entry_id}/move",
        response_model=ApiResponse[StorageEntryData],
        responses=_PROTECTED_RESPONSES,
        summary="Move a storage entry",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def move_entry(
        entry_id: UUID,
        payload: MoveEntryInput,
        request: Request,
    ) -> ApiResponse[StorageEntryData]:
        principal = require_principal(request)
        result = await use_cases.move_entry.execute(
            MoveEntryCommandDTO(
                principal.admin_id,
                entry_id,
                payload.destination_folder_id,
            )
        )
        return success_response(
            _entry_data(result), request_id=request.state.request_id
        )

    @router.post(
        "/entries/{entry_id}/copy",
        response_model=ApiResponse[StorageEntryData],
        status_code=status.HTTP_201_CREATED,
        responses=_PROTECTED_RESPONSES,
        summary="Copy a storage entry",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def copy_entry(
        entry_id: UUID,
        payload: CopyEntryInput,
        request: Request,
    ) -> ApiResponse[StorageEntryData]:
        principal = require_principal(request)
        result = await use_cases.copy_entry.execute(
            CopyEntryCommandDTO(
                principal.admin_id,
                entry_id,
                payload.destination_folder_id,
                payload.name,
            )
        )
        return success_response(
            _entry_data(result), request_id=request.state.request_id
        )

    @router.post(
        "/entries/{entry_id}/trash",
        response_model=ApiResponse[TrashItemData],
        responses=_PROTECTED_RESPONSES,
        summary="Move a storage entry to trash",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def trash_entry(
        entry_id: UUID,
        request: Request,
    ) -> ApiResponse[TrashItemData]:
        principal = require_principal(request)
        result = await use_cases.trash_entry.execute(
            TrashEntryCommandDTO(principal.admin_id, entry_id)
        )
        return success_response(
            _trash_data(result), request_id=request.state.request_id
        )

    @router.post(
        "/trash/{trash_item_id}/restore",
        response_model=ApiResponse[StorageEntryData],
        responses=_PROTECTED_RESPONSES,
        summary="Restore a trashed entry",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def restore_entry(
        trash_item_id: UUID,
        payload: RestoreTrashInput,
        request: Request,
    ) -> ApiResponse[StorageEntryData]:
        principal = require_principal(request)
        result = await use_cases.restore_entry.execute(
            RestoreEntryCommandDTO(
                principal.admin_id,
                trash_item_id,
                payload.destination_folder_id,
            )
        )
        return success_response(
            _entry_data(result), request_id=request.state.request_id
        )

    @router.delete(
        "/trash/{trash_item_id}",
        response_model=ApiResponse[PermanentDeleteData],
        responses=_PROTECTED_RESPONSES,
        summary="Permanently delete a trashed subtree",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def permanently_delete(
        trash_item_id: UUID,
        request: Request,
    ) -> ApiResponse[PermanentDeleteData]:
        principal = require_principal(request)
        result = await use_cases.permanently_delete.execute(
            PermanentlyDeleteCommandDTO(principal.admin_id, trash_item_id)
        )
        return success_response(
            PermanentDeleteData(deleted_entries=result.deleted_entries),
            request_id=request.state.request_id,
        )

    @router.post(
        "/uploads",
        response_model=ApiResponse[UploadSessionData],
        status_code=status.HTTP_201_CREATED,
        responses=_PROTECTED_RESPONSES,
        summary="Start a resumable upload",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def start_upload(
        payload: StartUploadInput,
        request: Request,
        response: Response,
    ) -> ApiResponse[UploadSessionData]:
        principal = require_principal(request)
        result = await use_cases.start_upload.execute(
            StartUploadCommandDTO(
                owner_id=principal.admin_id,
                parent_id=payload.parent_id,
                filename=payload.filename,
                expected_size=payload.size,
                declared_mime_type=payload.mime_type,
            )
        )
        response.headers["Location"] = str(
            request.url_for("get_upload_status", upload_id=result.id)
        )
        response.headers["Upload-Offset"] = str(result.uploaded_bytes)
        response.headers["Upload-Length"] = str(result.expected_size)
        return success_response(
            _upload_data(result),
            request_id=request.state.request_id,
        )

    @router.head(
        "/uploads/{upload_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=_PROTECTED_RESPONSES,
        summary="Get resumable upload offset",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def get_upload_status(upload_id: UUID, request: Request) -> Response:
        principal = require_principal(request)
        result = await use_cases.get_upload_status.execute(
            owner_id=principal.admin_id,
            upload_id=upload_id,
        )
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                "Upload-Offset": str(result.uploaded_bytes),
                "Upload-Length": str(result.expected_size),
                "Upload-Status": result.status,
                "Upload-Expires": result.expires_at.isoformat(),
            },
        )

    @router.patch(
        "/uploads/{upload_id}",
        response_model=ApiResponse[UploadChunkData],
        responses={
            **_PROTECTED_RESPONSES,
            415: {
                "model": ErrorResponse,
                "description": "Unsupported chunk media type.",
            },
        },
        summary="Append a streamed upload chunk",
        description=(
            "Streams application/offset+octet-stream at the exact Upload-Offset."
        ),
        openapi_extra=_chunk_openapi(csrf_header_name),
    )
    async def append_upload_chunk(
        upload_id: UUID,
        request: Request,
        response: Response,
        upload_offset: Annotated[int, Header(alias="Upload-Offset", ge=0)],
    ) -> ApiResponse[UploadChunkData]:
        if request.headers.get("content-type", "").partition(";")[0].casefold() != (
            "application/offset+octet-stream"
        ):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Content-Type must be application/offset+octet-stream.",
            )
        principal = require_principal(request)
        result = await use_cases.append_upload_chunk.execute(
            AppendUploadChunkCommandDTO(
                owner_id=principal.admin_id,
                upload_id=upload_id,
                offset=upload_offset,
                chunks=request.stream(),
            )
        )
        response.headers["Upload-Offset"] = str(result.offset)
        return success_response(
            _upload_chunk_data(result),
            request_id=request.state.request_id,
        )

    @router.post(
        "/uploads/{upload_id}/complete",
        response_model=ApiResponse[StorageEntryData],
        status_code=status.HTTP_201_CREATED,
        responses=_PROTECTED_RESPONSES,
        summary="Verify and atomically publish an upload",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def complete_upload(
        upload_id: UUID,
        request: Request,
    ) -> ApiResponse[StorageEntryData]:
        principal = require_principal(request)
        result = await use_cases.complete_upload.execute(
            CompleteUploadCommandDTO(principal.admin_id, upload_id)
        )
        return success_response(
            _entry_data(result),
            request_id=request.state.request_id,
        )

    @router.delete(
        "/uploads/{upload_id}",
        response_model=ApiResponse[UploadSessionData],
        responses=_PROTECTED_RESPONSES,
        summary="Cancel an upload and remove staging data",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def cancel_upload(
        upload_id: UUID,
        request: Request,
    ) -> ApiResponse[UploadSessionData]:
        principal = require_principal(request)
        result = await use_cases.cancel_upload.execute(
            CancelUploadCommandDTO(principal.admin_id, upload_id)
        )
        return success_response(
            _upload_data(result),
            request_id=request.state.request_id,
        )

    @router.get(
        "/files/{file_id}/content",
        response_class=StreamingResponse,
        responses=_download_responses(),
        summary="Stream file content",
        openapi_extra=_download_openapi(),
    )
    async def download_file(
        file_id: UUID,
        request: Request,
        disposition: Annotated[
            Literal["attachment", "inline"],
            Query(description="Content-Disposition mode for safe browser previews."),
        ] = "attachment",
    ) -> Response:
        return await _download_response(
            use_cases,
            file_id,
            request,
            head_only=False,
            disposition=disposition,
        )

    @router.head(
        "/files/{file_id}/content",
        responses=_download_responses(),
        summary="Inspect file delivery metadata",
        openapi_extra=_download_openapi(),
    )
    async def inspect_file(
        file_id: UUID,
        request: Request,
        disposition: Annotated[
            Literal["attachment", "inline"],
            Query(description="Content-Disposition mode for safe browser previews."),
        ] = "attachment",
    ) -> Response:
        return await _download_response(
            use_cases,
            file_id,
            request,
            head_only=True,
            disposition=disposition,
        )

    return router


def _entry_data(value: StorageEntryDTO) -> StorageEntryData:
    return StorageEntryData(
        id=value.id,
        parent_id=value.parent_id,
        kind=value.kind,
        name=value.name,
        size=value.size,
        mime_type=value.mime_type,
        extension=value.extension,
        checksum_sha256=value.checksum_sha256,
        current_version_number=value.current_version_number,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _file_data(value: FileDetailsDTO) -> FileDetailsData:
    return FileDetailsData(
        id=value.id,
        parent_id=value.parent_id,
        name=value.name,
        original_name=value.original_name,
        size=value.size,
        mime_type=value.mime_type,
        extension=value.extension,
        checksum_sha256=value.checksum_sha256,
        current_version_number=value.current_version_number,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _trash_data(value: TrashItemDTO) -> TrashItemData:
    return TrashItemData(
        id=value.id,
        entry_id=value.entry_id,
        original_parent_id=value.original_parent_id,
        trashed_at=value.trashed_at,
    )


def _upload_data(value: UploadSessionDTO) -> UploadSessionData:
    return UploadSessionData(
        id=value.id,
        parent_id=value.parent_id,
        filename=value.filename,
        expected_size=value.expected_size,
        uploaded_bytes=value.uploaded_bytes,
        declared_mime_type=value.declared_mime_type,
        extension=value.extension,
        status=value.status,
        expires_at=value.expires_at,
        checksum_sha256=value.checksum_sha256,
    )


def _upload_chunk_data(value: UploadChunkResultDTO) -> UploadChunkData:
    return UploadChunkData(
        upload_id=value.upload_id,
        offset=value.offset,
        received_bytes=value.received_bytes,
        chunk_sha256=value.chunk_sha256,
    )


def _mutation_openapi(csrf_header_name: str) -> dict[str, Any]:
    return {
        "security": _AUTH_SECURITY,
        "parameters": [
            {
                "name": csrf_header_name,
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": (
                    "Required for cookie-authenticated mutations; omitted for Bearer."
                ),
            }
        ],
    }


def _chunk_openapi(csrf_header_name: str) -> dict[str, Any]:
    contract = _mutation_openapi(csrf_header_name)
    contract["requestBody"] = {
        "required": True,
        "content": {
            "application/offset+octet-stream": {
                "schema": {"type": "string", "format": "binary"}
            }
        },
    }
    return contract


async def _download_response(
    use_cases: StorageRouteUseCases,
    file_id: UUID,
    request: Request,
    *,
    head_only: bool,
    disposition: Literal["attachment", "inline"] = "attachment",
) -> Response:
    principal = require_principal(request)
    file = await use_cases.prepare_download.execute(
        owner_id=principal.admin_id,
        file_id=file_id,
    )
    etag = file_etag(file)
    effective_disposition: Literal["attachment", "inline"] = (
        "inline"
        if disposition == "inline" and is_inline_media_type(file.mime_type)
        else "attachment"
    )
    headers = base_download_headers(
        file,
        etag=etag,
        disposition=effective_disposition,
    )
    request_headers = {
        name.casefold(): value for name, value in request.headers.items()
    }
    precondition = evaluate_preconditions(
        method="HEAD" if head_only else "GET",
        headers=request_headers,
        etag=etag,
        last_modified=file.updated_at,
    )
    if precondition == status.HTTP_304_NOT_MODIFIED:
        return Response(status_code=precondition, headers=headers)
    if precondition == status.HTTP_412_PRECONDITION_FAILED:
        return _download_error(
            request,
            status_code=precondition,
            code="http.precondition_failed",
            message="The file precondition failed.",
            headers=headers,
        )
    try:
        ranges = parse_ranges(request.headers.get("range"), size=file.size)
    except RangeRequestError:
        headers["Content-Range"] = f"bytes */{file.size}"
        return _download_error(
            request,
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            code="http.range_not_satisfiable",
            message="The requested byte range is not satisfiable.",
            headers=headers,
        )
    response_status = status.HTTP_200_OK
    boundary: str | None = None
    media_type = file.mime_type
    if len(ranges) == 1:
        selected = ranges[0]
        response_status = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = f"bytes {selected.start}-{selected.end}/{file.size}"
        headers["Content-Length"] = str(selected.length)
    elif len(ranges) > 1:
        response_status = status.HTTP_206_PARTIAL_CONTENT
        boundary = multipart_boundary(etag)
        media_type = f"multipart/byteranges; boundary={boundary}"
        headers["Content-Length"] = str(
            multipart_length(
                ranges,
                boundary=boundary,
                mime_type=file.mime_type,
                total_size=file.size,
            )
        )
    else:
        headers["Content-Length"] = str(file.size)
    headers["Content-Type"] = media_type
    redirect = use_cases.download_delivery.internal_redirect(file.storage_key)
    if redirect is not None:
        headers["X-Accel-Redirect"] = redirect.uri
        return Response(status_code=response_status, headers=headers)
    if head_only:
        return Response(status_code=response_status, headers=headers)
    body = stream_download(
        storage=use_cases.file_storage,
        file=file,
        ranges=ranges,
        boundary=boundary,
        metrics=use_cases.download_metrics,
    )
    return StreamingResponse(
        body,
        status_code=response_status,
        headers=headers,
        media_type=None,
    )


def _download_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str],
) -> JSONResponse:
    payload = error_response(
        ApiError(code=code, message=message),
        request_id=request.state.request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


def _download_responses() -> dict[int | str, dict[str, Any]]:
    return {
        **_PROTECTED_RESPONSES,
        200: {"description": "Complete file stream."},
        206: {"description": "Single or multipart byte range."},
        304: {"description": "Cached representation is current."},
        412: {"model": ErrorResponse, "description": "If-Match failed."},
        416: {"model": ErrorResponse, "description": "Range is not satisfiable."},
    }


def _download_openapi() -> dict[str, Any]:
    return {
        "security": _AUTH_SECURITY,
        "parameters": [
            {
                "name": "Range",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "example": "bytes=0-1048575",
            },
            {
                "name": "If-Match",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
            },
            {
                "name": "If-None-Match",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
            },
            {
                "name": "If-Modified-Since",
                "in": "header",
                "required": False,
                "schema": {"type": "string", "format": "http-date"},
            },
        ],
    }
