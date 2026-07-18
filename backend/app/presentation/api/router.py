"""Root API router factory."""

from fastapi import APIRouter

from app.application.use_cases.system import GetHealthUseCase, GetReadinessUseCase
from app.presentation.api.v1.auth import AuthRouteUseCases, create_auth_router
from app.presentation.api.v1.system import create_system_router
from app.presentation.auth import AuthCookiePolicy


def create_api_router(
    get_health: GetHealthUseCase,
    get_readiness: GetReadinessUseCase,
    auth_use_cases: AuthRouteUseCases,
    cookie_policy: AuthCookiePolicy,
) -> APIRouter:
    """Build routes from use cases injected by infrastructure."""
    router = APIRouter()
    router.include_router(
        create_system_router(get_health, get_readiness),
        tags=["system"],
    )
    router.include_router(
        create_auth_router(auth_use_cases, cookie_policy),
        tags=["authentication"],
    )
    return router
