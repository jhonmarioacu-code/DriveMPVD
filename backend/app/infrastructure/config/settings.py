"""Validated settings loaded exclusively from environment variables."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


_INSECURE_PRODUCTION_SECRET_MARKERS: Final = (
    "change-me",
    "development-",
    "replace-",
)


def _contains_insecure_placeholder(value: str) -> bool:
    normalized = value.casefold()
    return any(marker in normalized for marker in _INSECURE_PRODUCTION_SECRET_MARKERS)


class Settings(BaseSettings):
    """Single source of runtime configuration for every outer adapter."""

    model_config = SettingsConfigDict(
        env_prefix="DRIVEMPVD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="DriveMPVD", min_length=1, max_length=80)
    app_version: str = Field(default="0.1.0", min_length=1, max_length=32)
    environment: AppEnvironment = AppEnvironment.DEVELOPMENT
    api_prefix: str = "/api/v1"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://drivempvd:replace-me@localhost:5432/drivempvd"
    )
    database_pool_size: int = Field(default=10, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_statement_timeout_ms: int = Field(default=30_000, ge=1_000, le=300_000)
    database_echo: bool = False
    storage_root: Path = Path("/data/storage")
    storage_stream_block_size_bytes: int = Field(
        default=1024 * 1024,
        ge=64 * 1024,
        le=16 * 1024 * 1024,
    )
    storage_write_buffer_size_bytes: int = Field(
        default=1024 * 1024,
        ge=64 * 1024,
        le=16 * 1024 * 1024,
    )
    max_upload_size_bytes: int = Field(
        default=50 * 1024 * 1024 * 1024,
        gt=0,
    )
    max_upload_chunk_size_bytes: int = Field(
        default=16 * 1024 * 1024,
        ge=64 * 1024,
        le=256 * 1024 * 1024,
    )
    upload_session_ttl_seconds: int = Field(default=86_400, ge=300, le=604_800)
    max_logical_path_length: int = Field(default=4096, ge=255, le=16_384)
    upload_allowed_extensions: tuple[str, ...] = ()
    upload_blocked_extensions: tuple[str, ...] = (
        "bat",
        "cmd",
        "com",
        "dll",
        "exe",
        "msi",
        "ps1",
        "scr",
    )
    upload_allowed_mime_types: tuple[str, ...] = ()
    default_page_size: int = Field(default=50, ge=1, le=200)
    max_page_size: int = Field(default=200, ge=1, le=500)
    docs_enabled: bool = True
    jwt_issuer: str = "drivempvd"
    jwt_audience: str = "drivempvd-api"
    jwt_access_secret: SecretStr = SecretStr(
        "development-access-secret-change-me-32-bytes"
    )
    jwt_refresh_secret: SecretStr = SecretStr(
        "development-refresh-secret-change-me-32-bytes"
    )
    auth_secret_pepper: SecretStr = SecretStr(
        "development-auth-pepper-change-me-32-bytes"
    )
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        ge=3600,
        le=30 * 24 * 60 * 60,
    )
    argon2_time_cost: int = Field(default=3, ge=1, le=10)
    argon2_memory_cost_kib: int = Field(default=65_536, ge=19_456, le=262_144)
    argon2_parallelism: int = Field(default=2, ge=1, le=8)
    minimum_password_length: int = Field(default=12, ge=12, le=128)
    maximum_failed_logins: int = Field(default=5, ge=2, le=20)
    account_lock_seconds: int = Field(default=900, ge=60, le=86_400)
    login_rate_limit: int = Field(default=10, ge=1, le=100)
    login_rate_window_seconds: int = Field(default=60, ge=10, le=3600)
    login_rate_block_seconds: int = Field(default=300, ge=10, le=86_400)
    refresh_rate_limit: int = Field(default=30, ge=1, le=300)
    refresh_rate_window_seconds: int = Field(default=60, ge=10, le=3600)
    refresh_rate_block_seconds: int = Field(default=300, ge=10, le=86_400)
    auth_cookie_secure: bool = True
    auth_cookie_domain: str | None = None
    access_cookie_name: str = "drivempvd_access"
    refresh_cookie_name: str = "drivempvd_refresh"
    csrf_cookie_name: str = "drivempvd_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Require a normalized absolute API prefix."""
        if not value.startswith("/") or value.endswith("/"):
            msg = "api_prefix must start with '/' and must not end with '/'"
            raise ValueError(msg)
        return value

    @field_validator("storage_root")
    @classmethod
    def validate_storage_root(cls, value: Path) -> Path:
        """Reject relative storage roots before any file adapter starts."""
        if not value.is_absolute():
            msg = "storage_root must be an absolute path"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_page_sizes(self) -> Self:
        """Ensure the default page can never exceed the configured maximum."""
        if self.default_page_size > self.max_page_size:
            msg = "default_page_size must not exceed max_page_size"
            raise ValueError(msg)
        if self.environment is AppEnvironment.PRODUCTION:
            secrets = (
                self.jwt_access_secret.get_secret_value(),
                self.jwt_refresh_secret.get_secret_value(),
                self.auth_secret_pepper.get_secret_value(),
            )
            if any(
                len(secret) < 32 or _contains_insecure_placeholder(secret)
                for secret in secrets
            ) or len(set(secrets)) != len(secrets):
                msg = "production authentication secrets must be unique strong values"
                raise ValueError(msg)
            if _contains_insecure_placeholder(self.database_url.unicode_string()):
                msg = "production database URL must not contain an example placeholder"
                raise ValueError(msg)
            if not self.auth_cookie_secure:
                msg = "production authentication cookies must be Secure"
                raise ValueError(msg)
        return self


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and cache the validated environment configuration once."""
    return Settings()
