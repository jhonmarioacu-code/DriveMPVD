"""FastAPI application assembly performed by infrastructure."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.config import Settings, load_settings
from app.infrastructure.container import ApplicationContainer
from app.infrastructure.exceptions import InfrastructureError
from app.infrastructure.logging import configure_logging
from app.presentation.api.router import create_api_router
from app.presentation.errors.handlers import register_exception_handlers
from app.presentation.middleware.request_context import RequestContextMiddleware
from app.presentation.schemas.envelope import ErrorResponse


def _lifespan(
    container: ApplicationContainer,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.database.dispose()

    return lifespan


def create_application(settings: Settings | None = None) -> FastAPI:
    """Build an ASGI application from validated settings and injected use cases."""
    active_settings = settings or load_settings()
    configure_logging(active_settings)
    container = ApplicationContainer.build(active_settings)

    docs_url = "/docs" if active_settings.docs_enabled else None
    redoc_url = "/redoc" if active_settings.docs_enabled else None
    openapi_url = "/openapi.json" if active_settings.docs_enabled else None
    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=_lifespan(container),
        responses={
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(
        app,
        infrastructure_error_type=InfrastructureError,
    )
    app.include_router(
        create_api_router(container.get_health, container.get_readiness),
        prefix=active_settings.api_prefix,
    )
    return app
