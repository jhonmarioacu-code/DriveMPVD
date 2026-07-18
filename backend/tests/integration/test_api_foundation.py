from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.exceptions import ConflictError
from app.domain.exceptions import DomainError
from app.infrastructure.bootstrap import create_application
from app.infrastructure.config.settings import AppEnvironment, Settings
from app.infrastructure.exceptions import InfrastructureError


@pytest.fixture
def app() -> FastAPI:
    settings = Settings(
        app_name="DriveMPVD Test",
        app_version="1.2.3",
        environment=AppEnvironment.TEST,
        storage_root="C:/test-storage",
    )
    application = create_application(settings)

    @application.get("/test/domain-error", include_in_schema=False)
    async def raise_domain_error() -> None:
        raise DomainError("Domain rejected the operation.")

    @application.get("/test/conflict", include_in_schema=False)
    async def raise_conflict() -> None:
        raise ConflictError()

    @application.get("/test/infrastructure-error", include_in_schema=False)
    async def raise_infrastructure_error() -> None:
        raise InfrastructureError()

    @application.get("/test/validation", include_in_schema=False)
    async def validate_query(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @application.get("/test/unexpected-error", include_in_schema=False)
    async def raise_unexpected_error() -> None:
        raise RuntimeError("private detail")

    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_health_uses_uniform_envelope_and_request_id(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "test-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-123"
    assert response.json() == {
        "data": {
            "status": "ok",
            "service": "DriveMPVD Test",
            "version": "1.2.3",
        },
        "error": None,
        "meta": {"request_id": "test-123", "next_cursor": None},
    }


async def test_invalid_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "invalid request id with spaces"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "invalid request id with spaces"
    assert response.json()["meta"]["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.parametrize(
    ("path", "status_code", "error_code"),
    [
        ("/test/domain-error", 422, "domain.invariant_violation"),
        ("/test/conflict", 409, "application.conflict"),
        ("/test/infrastructure-error", 503, "infrastructure.unavailable"),
        ("/does-not-exist", 404, "http.404"),
    ],
)
async def test_global_errors_use_uniform_envelope(
    client: AsyncClient,
    path: str,
    status_code: int,
    error_code: str,
) -> None:
    response = await client.get(path)
    payload = response.json()

    assert response.status_code == status_code
    assert payload["data"] is None
    assert payload["error"]["code"] == error_code
    assert payload["meta"]["request_id"] == response.headers["X-Request-ID"]


async def test_request_validation_uses_uniform_envelope(client: AsyncClient) -> None:
    response = await client.get("/test/validation", params={"limit": "invalid"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request.validation_error"
    assert response.json()["error"]["details"][0]["field"] == "query.limit"


async def test_unexpected_errors_are_sanitized(client: AsyncClient) -> None:
    response = await client.get("/test/unexpected-error")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal.error",
        "message": "An unexpected error occurred.",
        "details": [],
    }
    assert "private detail" not in response.text


async def test_openapi_is_the_source_for_interactive_documentation(
    client: AsyncClient,
) -> None:
    openapi_response = await client.get("/openapi.json")
    docs_response = await client.get("/docs")

    assert openapi_response.status_code == 200
    assert docs_response.status_code == 200
    schema = openapi_response.json()
    health_operation = schema["paths"]["/api/v1/health"]["get"]
    assert health_operation["summary"] == "Check API liveness"
    assert "ApiResponse_HealthData_" in schema["components"]["schemas"]
