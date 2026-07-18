"""System-level application DTOs."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class HealthStatusDTO:
    """Health information independent of the HTTP representation."""

    status: Literal["ok"]
    service: str
    version: str


@dataclass(frozen=True, slots=True)
class ReadinessStatusDTO:
    """Readiness result after checking required infrastructure."""

    status: Literal["ready"]
    database: Literal["available"]
