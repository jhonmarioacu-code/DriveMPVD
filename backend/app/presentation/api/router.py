"""Root API router factory."""

from fastapi import APIRouter

from app.application.use_cases.system import GetHealthUseCase, GetReadinessUseCase
from app.presentation.api.v1.system import create_system_router


def create_api_router(
    get_health: GetHealthUseCase,
    get_readiness: GetReadinessUseCase,
) -> APIRouter:
    """Build routes from use cases injected by infrastructure."""
    router = APIRouter()
    router.include_router(
        create_system_router(get_health, get_readiness),
        tags=["system"],
    )
    return router
