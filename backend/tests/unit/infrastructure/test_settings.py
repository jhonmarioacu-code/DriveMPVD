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

    settings = Settings(_env_file=None)

    assert settings.app_name == "Personal Drive"
    assert settings.environment is AppEnvironment.TEST
    assert settings.api_prefix == "/api/test"
    assert settings.default_page_size == 25
    assert settings.max_page_size == 100


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


def test_production_accepts_three_independent_strong_auth_secrets() -> None:
    settings = Settings(
        environment=AppEnvironment.PRODUCTION,
        storage_root=Path.cwd().anchor,
        jwt_access_secret="a" * 40,
        jwt_refresh_secret="b" * 40,
        auth_secret_pepper="c" * 40,
    )

    assert settings.environment is AppEnvironment.PRODUCTION
