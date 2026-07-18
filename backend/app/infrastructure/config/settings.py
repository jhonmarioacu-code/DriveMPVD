"""Validated settings loaded exclusively from environment variables."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


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
    storage_root: Path = Path("/data/storage")
    max_upload_size_bytes: int = Field(
        default=50 * 1024 * 1024 * 1024,
        gt=0,
    )
    default_page_size: int = Field(default=50, ge=1, le=200)
    max_page_size: int = Field(default=200, ge=1, le=500)
    docs_enabled: bool = True

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
        return self


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and cache the validated environment configuration once."""
    return Settings()
