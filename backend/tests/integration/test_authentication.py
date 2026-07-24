from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.application.dtos.auth import (
    BootstrapAdminCommandDTO,
    ChangeAdminPasswordCommandDTO,
    LoginCommandDTO,
    RefreshCommandDTO,
)
from app.application.exceptions import (
    ConflictError,
    CsrfValidationError,
    SessionRevokedError,
)
from app.infrastructure.bootstrap import create_application
from app.infrastructure.config.settings import AppEnvironment, Settings
from app.infrastructure.container import ApplicationContainer

pytestmark = pytest.mark.postgresql


@dataclass(slots=True)
class AuthTestContext:
    client: AsyncClient
    container: ApplicationContainer


@pytest.fixture
async def auth_context(
    migrated_database_url: str,
    clean_auth: None,
) -> AsyncIterator[AuthTestContext]:
    del clean_auth
    settings = Settings(
        environment=AppEnvironment.TEST,
        database_url=migrated_database_url,
        storage_root=Path.cwd().anchor,
        database_pool_size=2,
        database_max_overflow=0,
        argon2_time_cost=1,
        argon2_memory_cost_kib=19_456,
        argon2_parallelism=1,
        jwt_access_secret="a" * 40,
        jwt_refresh_secret="b" * 40,
        auth_secret_pepper="c" * 40,
        auth_cookie_secure=False,
        maximum_failed_logins=2,
        account_lock_seconds=60,
        login_rate_limit=3,
        login_rate_window_seconds=60,
        login_rate_block_seconds=60,
        refresh_rate_limit=5,
    )
    container = ApplicationContainer.build(settings)
    await container.bootstrap_admin.execute(
        BootstrapAdminCommandDTO(
            username="Admin",
            password="correct horse battery staple",
        )
    )
    application = create_application(settings, container=container)
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield AuthTestContext(client=client, container=container)
    await container.database.dispose()


async def test_bearer_login_refresh_rotation_and_reuse_revocation(
    auth_context: AuthTestContext,
) -> None:
    login = await auth_context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "correct horse battery staple",
            "delivery": "bearer",
        },
    )
    assert login.status_code == 200
    first_tokens = login.json()["data"]
    assert first_tokens["access_token"]
    assert first_tokens["refresh_token"]
    assert "drivempvd_access" not in login.cookies

    session = await auth_context.client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
    )
    assert session.status_code == 200
    assert session.json()["data"]["username"] == "Admin"

    refresh = await auth_context.client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": first_tokens["refresh_token"],
            "delivery": "bearer",
        },
    )
    assert refresh.status_code == 200
    rotated_tokens = refresh.json()["data"]
    assert rotated_tokens["refresh_token"] != first_tokens["refresh_token"]

    reuse = await auth_context.client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": first_tokens["refresh_token"],
            "delivery": "bearer",
        },
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "auth.session_revoked"

    revoked_access = await auth_context.client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"},
    )
    assert revoked_access.status_code == 401


async def test_cookie_auth_requires_csrf_and_logout_revokes_session(
    auth_context: AuthTestContext,
) -> None:
    login = await auth_context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "Admin",
            "password": "correct horse battery staple",
        },
    )
    assert login.status_code == 200
    assert login.json()["data"]["access_token"] is None
    assert auth_context.client.cookies.get("drivempvd_access")
    csrf = auth_context.client.cookies.get("drivempvd_csrf")
    assert csrf

    rejected_refresh = await auth_context.client.post("/api/v1/auth/refresh", json={})
    assert rejected_refresh.status_code == 403

    refreshed = await auth_context.client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={"X-CSRF-Token": csrf},
    )
    assert refreshed.status_code == 200
    csrf = auth_context.client.cookies.get("drivempvd_csrf")
    assert csrf

    rejected = await auth_context.client.post("/api/v1/auth/logout")
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "auth.csrf_validation_failed"

    logout = await auth_context.client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert logout.status_code == 200

    current = await auth_context.client.get("/api/v1/auth/session")
    assert current.status_code == 401
    assert current.headers["WWW-Authenticate"] == "Bearer"


async def test_lockout_rate_limit_security_events_and_openapi(
    auth_context: AuthTestContext,
) -> None:
    for expected_status in (401, 429):
        response = await auth_context.client.post(
            "/api/v1/auth/login",
            json={"username": "Admin", "password": "wrong password"},
        )
        assert response.status_code == expected_status

    locked = await auth_context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "Admin",
            "password": "correct horse battery staple",
        },
    )
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0

    rate_limited = await auth_context.client.post(
        "/api/v1/auth/login",
        json={"username": "Admin", "password": "anything"},
    )
    assert rate_limited.status_code == 429
    assert rate_limited.json()["error"]["code"] == "auth.rate_limit_exceeded"

    async with auth_context.container.database.engine.connect() as connection:
        event_types = set(
            await connection.scalars(text("SELECT event_type FROM security_events"))
        )
    assert "admin.created" in event_types
    assert "auth.login_failed" in event_types

    openapi = (await auth_context.client.get("/openapi.json")).json()
    schemes = openapi["components"]["securitySchemes"]
    assert schemes["BearerAuth"]["scheme"] == "bearer"
    assert schemes["AccessCookie"]["in"] == "cookie"


async def test_revoke_all_sessions_invalidates_every_access_token(
    auth_context: AuthTestContext,
) -> None:
    with pytest.raises(ConflictError):
        await auth_context.container.bootstrap_admin.execute(
            BootstrapAdminCommandDTO(
                username="SecondAdmin",
                password="another correct horse password",
            )
        )

    access_tokens: list[str] = []
    for _ in range(2):
        login = await auth_context.client.post(
            "/api/v1/auth/login",
            json={
                "username": "Admin",
                "password": "correct horse battery staple",
                "delivery": "bearer",
            },
        )
        access_tokens.append(login.json()["data"]["access_token"])

    revoke = await auth_context.client.post(
        "/api/v1/auth/sessions/revoke-all",
        headers={"Authorization": f"Bearer {access_tokens[-1]}"},
    )

    assert revoke.status_code == 200
    assert revoke.json()["data"]["revoked_sessions"] == 2
    for token in access_tokens:
        current = await auth_context.client.get(
            "/api/v1/auth/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert current.status_code == 401


async def test_unknown_and_disabled_accounts_fail_without_disclosing_identity(
    auth_context: AuthTestContext,
) -> None:
    unknown = await auth_context.client.post(
        "/api/v1/auth/login",
        json={"username": "does-not-exist", "password": "irrelevant password"},
    )
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "auth.invalid_credentials"

    async with auth_context.container.database.engine.begin() as connection:
        await connection.execute(text("UPDATE admin_accounts SET enabled = FALSE"))
    disabled = await auth_context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "Admin",
            "password": "correct horse battery staple",
            "delivery": "bearer",
        },
    )
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "auth.account_disabled"


async def test_disabling_account_invalidates_access_and_refresh_tokens(
    auth_context: AuthTestContext,
) -> None:
    login = await auth_context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "Admin",
            "password": "correct horse battery staple",
            "delivery": "bearer",
        },
    )
    tokens = login.json()["data"]
    async with auth_context.container.database.engine.begin() as connection:
        await connection.execute(text("UPDATE admin_accounts SET enabled = FALSE"))

    current = await auth_context.client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert current.status_code == 403
    assert current.json()["error"]["code"] == "auth.account_disabled"
    refreshed = await auth_context.client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"], "delivery": "bearer"},
    )
    assert refreshed.status_code == 403
    assert refreshed.json()["error"]["code"] == "auth.account_disabled"


async def test_refresh_use_case_rejects_invalid_cookie_csrf_proof(
    auth_context: AuthTestContext,
) -> None:
    login = await auth_context.container.login.execute(
        LoginCommandDTO(
            username="Admin",
            password="correct horse battery staple",
            client_ip="198.51.100.25",
            user_agent="integration-test",
        )
    )

    with pytest.raises(CsrfValidationError):
        await auth_context.container.refresh_session.execute(
            RefreshCommandDTO(
                refresh_token=login.refresh_token.value,
                client_ip="198.51.100.25",
                user_agent="integration-test",
                csrf_cookie=login.csrf_token,
                csrf_header="wrong-csrf-token",
                used_cookie=True,
            )
        )


async def test_direct_authentication_refresh_and_logout_lifecycle(
    auth_context: AuthTestContext,
) -> None:
    login = await auth_context.container.login.execute(
        LoginCommandDTO(
            username="Admin",
            password="correct horse battery staple",
            client_ip="198.51.100.26",
            user_agent="integration-test",
        )
    )

    principal = await auth_context.container.authenticate_access.execute(
        login.access_token.value,
        authenticated_via_cookie=False,
    )
    assert principal.username == "Admin"
    assert principal.session_id == login.session_id

    with pytest.raises(CsrfValidationError):
        await auth_context.container.authenticate_access.execute(
            login.access_token.value,
            authenticated_via_cookie=True,
            require_csrf=True,
            csrf_cookie=login.csrf_token,
            csrf_header="wrong-csrf-token",
        )

    rotated = await auth_context.container.refresh_session.execute(
        RefreshCommandDTO(
            refresh_token=login.refresh_token.value,
            client_ip="198.51.100.26",
            user_agent="integration-test",
            csrf_cookie=login.csrf_token,
            csrf_header=login.csrf_token,
            used_cookie=True,
        )
    )
    assert rotated.refresh_token.value != login.refresh_token.value

    rotated_principal = await auth_context.container.authenticate_access.execute(
        rotated.access_token.value,
        authenticated_via_cookie=False,
    )
    await auth_context.container.logout.execute(
        rotated_principal,
        client_ip="198.51.100.26",
        user_agent="integration-test",
    )

    with pytest.raises(SessionRevokedError):
        await auth_context.container.authenticate_access.execute(
            rotated.access_token.value,
            authenticated_via_cookie=False,
        )


async def test_local_password_rotation_revokes_sessions_and_audits_change(
    auth_context: AuthTestContext,
) -> None:
    login = await auth_context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "Admin",
            "password": "correct horse battery staple",
            "delivery": "bearer",
        },
    )
    old_access_token = login.json()["data"]["access_token"]

    account = await auth_context.container.change_admin_password.execute(
        ChangeAdminPasswordCommandDTO(
            username="admin",
            password="new correct horse battery password",
        )
    )
    assert account.failed_login_attempts == 0
    assert account.locked_until is None

    revoked = await auth_context.client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert revoked.status_code == 401

    old_password = await auth_context.client.post(
        "/api/v1/auth/login",
        json={"username": "Admin", "password": "correct horse battery staple"},
    )
    assert old_password.status_code == 401
    new_password = await auth_context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "Admin",
            "password": "new correct horse battery password",
        },
    )
    assert new_password.status_code == 200

    async with auth_context.container.database.engine.connect() as connection:
        changed_events = await connection.scalar(
            text(
                "SELECT COUNT(*) FROM security_events "
                "WHERE event_type = 'admin.password_changed'"
            )
        )
    assert changed_events == 1
