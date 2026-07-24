"""HTTP adapter for private favorites and recent opens."""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.application.dtos.activity import (
    ActivityEntryDTO,
    FavoriteStatusDTO,
    ListActivityQueryDTO,
    RecordRecentOpenCommandDTO,
)
from app.application.use_cases.activity import (
    ListActivityUseCase,
    RecordRecentOpenUseCase,
    RemoveFavoriteUseCase,
    SetFavoriteUseCase,
)
from app.presentation.auth import require_principal
from app.presentation.schemas.activity import (
    ActivityEntriesData,
    ActivityEntryData,
    ActivityListQuery,
    FavoriteStatusData,
    RecentOpenData,
)
from app.presentation.schemas.envelope import (
    ApiResponse,
    ErrorResponse,
    success_response,
)
from app.presentation.schemas.storage import StorageEntryData

_AUTH_SECURITY: list[dict[str, list[str]]] = [
    {"BearerAuth": []},
    {"AccessCookie": []},
]
_PROTECTED_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "CSRF validation failed."},
    404: {"model": ErrorResponse, "description": "The resource was not found."},
    422: {"model": ErrorResponse, "description": "The request is invalid."},
}


@dataclass(frozen=True, slots=True)
class ActivityRouteUseCases:
    list_favorites: ListActivityUseCase
    list_recents: ListActivityUseCase
    set_favorite: SetFavoriteUseCase
    remove_favorite: RemoveFavoriteUseCase
    record_recent_open: RecordRecentOpenUseCase


def create_activity_router(
    use_cases: ActivityRouteUseCases,
    *,
    csrf_header_name: str,
) -> APIRouter:
    router = APIRouter(prefix="/activity")

    @router.get(
        "/favorites",
        response_model=ApiResponse[ActivityEntriesData],
        responses=_PROTECTED_RESPONSES,
        summary="List active favorites with keyset pagination",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def list_favorites(
        query: Annotated[ActivityListQuery, Query()],
        request: Request,
    ) -> ApiResponse[ActivityEntriesData]:
        principal = require_principal(request)
        page = await use_cases.list_favorites.execute(
            ListActivityQueryDTO(
                owner_id=principal.admin_id,
                limit=query.limit,
                cursor=query.cursor,
            )
        )
        return success_response(
            ActivityEntriesData(
                items=tuple(_activity_entry_data(item) for item in page.items)
            ),
            request_id=request.state.request_id,
            next_cursor=page.next_cursor,
        )

    @router.put(
        "/favorites/{entry_id}",
        response_model=ApiResponse[FavoriteStatusData],
        responses=_PROTECTED_RESPONSES,
        summary="Mark an active storage entry as favorite",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def set_favorite(
        entry_id: UUID,
        request: Request,
    ) -> ApiResponse[FavoriteStatusData]:
        principal = require_principal(request)
        result = await use_cases.set_favorite.execute(
            owner_id=principal.admin_id,
            entry_id=entry_id,
        )
        return success_response(
            _favorite_status_data(result),
            request_id=request.state.request_id,
        )

    @router.delete(
        "/favorites/{entry_id}",
        response_model=ApiResponse[FavoriteStatusData],
        responses=_PROTECTED_RESPONSES,
        summary="Remove an active storage entry from favorites",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def remove_favorite(
        entry_id: UUID,
        request: Request,
    ) -> ApiResponse[FavoriteStatusData]:
        principal = require_principal(request)
        result = await use_cases.remove_favorite.execute(
            owner_id=principal.admin_id,
            entry_id=entry_id,
        )
        return success_response(
            _favorite_status_data(result),
            request_id=request.state.request_id,
        )

    @router.get(
        "/recents",
        response_model=ApiResponse[ActivityEntriesData],
        responses=_PROTECTED_RESPONSES,
        summary="List recently opened active storage entries",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def list_recents(
        query: Annotated[ActivityListQuery, Query()],
        request: Request,
    ) -> ApiResponse[ActivityEntriesData]:
        principal = require_principal(request)
        page = await use_cases.list_recents.execute(
            ListActivityQueryDTO(
                owner_id=principal.admin_id,
                limit=query.limit,
                cursor=query.cursor,
            )
        )
        return success_response(
            ActivityEntriesData(
                items=tuple(_activity_entry_data(item) for item in page.items)
            ),
            request_id=request.state.request_id,
            next_cursor=page.next_cursor,
        )

    @router.post(
        "/recents/{entry_id}",
        response_model=ApiResponse[RecentOpenData],
        responses=_PROTECTED_RESPONSES,
        summary="Record one explicit user open without touching file delivery ranges",
        openapi_extra=_mutation_openapi(csrf_header_name),
    )
    async def record_recent_open(
        entry_id: UUID,
        request: Request,
    ) -> ApiResponse[RecentOpenData]:
        principal = require_principal(request)
        await use_cases.record_recent_open.execute(
            RecordRecentOpenCommandDTO(
                owner_id=principal.admin_id,
                entry_id=entry_id,
            )
        )
        return success_response(
            RecentOpenData(entry_id=entry_id),
            request_id=request.state.request_id,
        )

    return router


def _entry_data(value: ActivityEntryDTO) -> StorageEntryData:
    entry = value.entry
    return StorageEntryData(
        id=entry.id,
        parent_id=entry.parent_id,
        kind=entry.kind,
        name=entry.name,
        size=entry.size,
        mime_type=entry.mime_type,
        extension=entry.extension,
        checksum_sha256=entry.checksum_sha256,
        current_version_number=entry.current_version_number,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        is_favorite=entry.is_favorite,
    )


def _activity_entry_data(value: ActivityEntryDTO) -> ActivityEntryData:
    return ActivityEntryData(entry=_entry_data(value), occurred_at=value.occurred_at)


def _favorite_status_data(value: FavoriteStatusDTO) -> FavoriteStatusData:
    return FavoriteStatusData(entry_id=value.entry_id, is_favorite=value.is_favorite)


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
