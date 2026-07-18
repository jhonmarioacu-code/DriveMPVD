"""HTTP adapter for storage metadata commands and queries."""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from app.application.dtos.storage import (
    CopyEntryCommandDTO,
    CreateFolderCommandDTO,
    FileDetailsDTO,
    ListFolderEntriesQueryDTO,
    MoveEntryCommandDTO,
    PermanentlyDeleteCommandDTO,
    RenameEntryCommandDTO,
    RestoreEntryCommandDTO,
    StorageEntryDTO,
    StorageListFiltersDTO,
    TrashEntryCommandDTO,
    TrashItemDTO,
)
from app.application.use_cases.storage import (
    CopyEntryUseCase,
    CreateFolderUseCase,
    GetFileDetailsUseCase,
    ListFolderEntriesUseCase,
    MoveEntryUseCase,
    PermanentlyDeleteUseCase,
    RenameEntryUseCase,
    RestoreEntryUseCase,
    TrashEntryUseCase,
)
from app.presentation.auth import require_principal
from app.presentation.http_cache import (
    apply_cache_headers,
    conditional_not_modified,
    metadata_etag,
)
from app.presentation.schemas.envelope import (
    ApiResponse,
    ErrorResponse,
    success_response,
)
from app.presentation.schemas.storage import (
    CopyEntryInput,
    CreateFolderInput,
    FileDetailsData,
    FolderEntriesData,
    FolderEntriesQuery,
    MoveEntryInput,
    PermanentDeleteData,
    RenameEntryInput,
    RestoreTrashInput,
    StorageEntryData,
    TrashItemData,
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
    list_entries: ListFolderEntriesUseCase
    get_file: GetFileDetailsUseCase
    create_folder: CreateFolderUseCase
    rename_entry: RenameEntryUseCase
    move_entry: MoveEntryUseCase
    copy_entry: CopyEntryUseCase
    trash_entry: TrashEntryUseCase
    restore_entry: RestoreEntryUseCase
    permanently_delete: PermanentlyDeleteUseCase


def create_storage_router(
    use_cases: StorageRouteUseCases,
    *,
    csrf_header_name: str,
) -> APIRouter:
    router = APIRouter(prefix="/storage")

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
