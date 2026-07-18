"""Authentication HTTP schemas generated into OpenAPI."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)
    delivery: Literal["cookie", "bearer"] = "cookie"


class RefreshInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = Field(default=None, max_length=8192)
    delivery: Literal["cookie", "bearer"] = "cookie"


class AuthenticationData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    token_type: Literal["Bearer"] = "Bearer"
    access_token: str | None = None
    refresh_token: str | None = None
    access_expires_at: datetime
    refresh_expires_at: datetime


class SessionData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    admin_id: UUID
    session_id: UUID
    username: str


class RevocationData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    revoked_sessions: int = Field(ge=0)
