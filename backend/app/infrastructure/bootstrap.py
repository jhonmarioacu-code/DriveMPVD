"""FastAPI application assembly performed by infrastructure."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.config import Settings, load_settings
from app.infrastructure.container import ApplicationContainer
from app.infrastructure.exceptions import InfrastructureError
from app.infrastructure.logging import configure_logging
from app.presentation.api.router import create_api_router
from app.presentation.api.v1.auth import AuthRouteUseCases
from app.presentation.auth import AuthCookiePolicy
from app.presentation.errors.handlers import register_exception_handlers
from app.presentation.middleware.authentication import AuthenticationMiddleware
from app.presentation.middleware.request_context import RequestContextMiddleware
from app.presentation.openapi import configure_auth_openapi
from app.presentation.schemas.envelope import ErrorResponse


def _lifespan(
    container: ApplicationContainer,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.database.dispose()

    return lifespan


def create_application(
    settings: Settings | None = None,
    *,
    container: ApplicationContainer | None = None,
) -> FastAPI:
    """Build an ASGI application from validated settings and injected use cases."""
    active_settings = settings or load_settings()
    configure_logging(active_settings)
    active_container = container or ApplicationContainer.build(active_settings)

    docs_url = "/docs" if active_settings.docs_enabled else None
    redoc_url = "/redoc" if active_settings.docs_enabled else None
    openapi_url = "/openapi.json" if active_settings.docs_enabled else None
    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=_lifespan(active_container),
        responses={
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    cookie_policy = AuthCookiePolicy(
        secure=active_settings.auth_cookie_secure,
        domain=active_settings.auth_cookie_domain,
        access_name=active_settings.access_cookie_name,
        refresh_name=active_settings.refresh_cookie_name,
        csrf_name=active_settings.csrf_cookie_name,
        csrf_header_name=active_settings.csrf_header_name,
        access_max_age=active_settings.access_token_ttl_seconds,
        refresh_max_age=active_settings.refresh_token_ttl_seconds,
        refresh_path=f"{active_settings.api_prefix}/auth",
    )
    auth_use_cases = AuthRouteUseCases(
        login=active_container.login,
        refresh=active_container.refresh_session,
        logout=active_container.logout,
        revoke_all=active_container.revoke_all_sessions,
    )
    app.add_middleware(
        AuthenticationMiddleware,
        authenticate=active_container.authenticate_access,
        access_cookie_name=cookie_policy.access_name,
        csrf_cookie_name=cookie_policy.csrf_name,
        csrf_header_name=cookie_policy.csrf_header_name,
        csrf_exempt_paths=frozenset(
            {
                f"{active_settings.api_prefix}/auth/login",
                f"{active_settings.api_prefix}/auth/refresh",
            }
        ),
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(
        app,
        infrastructure_error_type=InfrastructureError,
    )
    app.include_router(
        create_api_router(
            active_container.get_health,
            active_container.get_readiness,
            auth_use_cases,
            cookie_policy,
        ),
        prefix=active_settings.api_prefix,
    )
    configure_auth_openapi(
        app,
        access_cookie_name=active_settings.access_cookie_name,
    )
    return app
