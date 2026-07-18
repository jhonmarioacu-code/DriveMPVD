"""System HTTP schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthData(BaseModel):
    """Public health payload generated into OpenAPI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"]
    service: str
    version: str
