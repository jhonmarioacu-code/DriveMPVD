from pathlib import Path

import pytest
from pydantic import ValidationError

from app.infrastructure.config.settings import AppEnvironment, Settings


def test_settings_load_all_runtime_values_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DRIVEMPVD_APP_NAME", "Personal Drive")
    monkeypatch.setenv("DRIVEMPVD_ENVIRONMENT", "test")
    monkeypatch.setenv("DRIVEMPVD_API_PREFIX", "/api/test")
    monkeypatch.setenv("DRIVEMPVD_STORAGE_ROOT", str(Path.cwd().anchor))
    monkeypatch.setenv("DRIVEMPVD_DEFAULT_PAGE_SIZE", "25")
    monkeypatch.setenv("DRIVEMPVD_MAX_PAGE_SIZE", "100")
    monkeypatch.setenv("DRIVEMPVD_OUTBOX_WORKER_POLL_SECONDS", "10")
    monkeypatch.setenv("DRIVEMPVD_OUTBOX_WORKER_EVENT_BATCH_SIZE", "20")
    monkeypatch.setenv("DRIVEMPVD_OUTBOX_ORPHAN_SWEEP_BATCH_SIZE", "30")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Personal Drive"
    assert settings.environment is AppEnvironment.TEST
    assert settings.api_prefix == "/api/test"
    assert settings.default_page_size == 25
    assert settings.max_page_size == 100
    assert settings.outbox_worker_poll_seconds == 10
    assert settings.outbox_worker_event_batch_size == 20
    assert settings.outbox_orphan_sweep_batch_size == 30


def test_settings_reject_relative_storage_root() -> None:
    with pytest.raises(ValidationError):
        Settings(storage_root=Path("relative/storage"))


@pytest.mark.parametrize("api_prefix", ["api/v1", "/api/v1/"])
def test_settings_reject_invalid_api_prefix(api_prefix: str) -> None:
    with pytest.raises(ValidationError):
        Settings(api_prefix=api_prefix)


def test_settings_reject_default_page_larger_than_maximum() -> None:
    with pytest.raises(ValidationError):
        Settings(default_page_size=100, max_page_size=50)


def test_settings_allows_a_write_buffer_larger_than_a_network_chunk() -> None:
    settings = Settings(
        storage_root=Path.cwd().anchor,
        max_upload_chunk_size_bytes=64 * 1024,
    )

    assert settings.storage_write_buffer_size_bytes == 1024 * 1024


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("outbox_worker_poll_seconds", 0),
        ("outbox_worker_event_batch_size", 0),
        ("outbox_worker_event_batch_size", 201),
        ("outbox_orphan_sweep_batch_size", 0),
        ("outbox_orphan_sweep_batch_size", 1_001),
    ],
)
def test_settings_reject_invalid_outbox_worker_bounds(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        _settings_with_outbox_value(field, value)


def _settings_with_outbox_value(field: str, value: int) -> Settings:
    if field == "outbox_worker_poll_seconds":
        return Settings(
            storage_root=Path.cwd().anchor,
            outbox_worker_poll_seconds=value,
        )
    if field == "outbox_worker_event_batch_size":
        return Settings(
            storage_root=Path.cwd().anchor,
            outbox_worker_event_batch_size=value,
        )
    return Settings(
        storage_root=Path.cwd().anchor,
        outbox_orphan_sweep_batch_size=value,
    )


def test_production_rejects_default_duplicate_or_short_auth_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment=AppEnvironment.PRODUCTION,
            storage_root=Path.cwd().anchor,
        )

    with pytest.raises(ValidationError):
        Settings(
            environment=AppEnvironment.PRODUCTION,
            storage_root=Path.cwd().anchor,
            jwt_access_secret="x" * 40,
            jwt_refresh_secret="x" * 40,
            auth_secret_pepper="z" * 40,
        )


@pytest.mark.parametrize(
    "placeholder",
    [
        "replace-with-a-unique-32-byte-access-secret",
        "development-access-secret-change-me-32-bytes",
    ],
)
def test_production_rejects_example_auth_secrets(placeholder: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment=AppEnvironment.PRODUCTION,
            storage_root=Path.cwd().anchor,
            jwt_access_secret=placeholder,
            jwt_refresh_secret="b" * 40,
            auth_secret_pepper="c" * 40,
        )


def test_production_rejects_example_database_url_and_insecure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment=AppEnvironment.PRODUCTION,
            storage_root=Path.cwd().anchor,
            jwt_access_secret="a" * 40,
            jwt_refresh_secret="b" * 40,
            auth_secret_pepper="c" * 40,
            database_url="postgresql+asyncpg://drivempvd:replace-with-password@postgres:5432/drivempvd",
        )
    with pytest.raises(ValidationError):
        Settings(
            environment=AppEnvironment.PRODUCTION,
            storage_root=Path.cwd().anchor,
            jwt_access_secret="a" * 40,
            jwt_refresh_secret="b" * 40,
            auth_secret_pepper="c" * 40,
            auth_cookie_secure=False,
        )


def test_production_accepts_three_independent_strong_auth_secrets() -> None:
    settings = Settings(
        environment=AppEnvironment.PRODUCTION,
        storage_root=Path.cwd().anchor,
        jwt_access_secret="a" * 40,
        jwt_refresh_secret="b" * 40,
        auth_secret_pepper="c" * 40,
        database_url="postgresql+asyncpg://drivempvd:database-password@postgres:5432/drivempvd",
    )

    assert settings.environment is AppEnvironment.PRODUCTION
