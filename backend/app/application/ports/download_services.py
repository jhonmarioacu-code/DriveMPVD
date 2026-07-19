"""Download delivery and observability boundaries."""

from dataclasses import dataclass
from typing import Protocol

from app.application.ports.file_storage import StorageKey


@dataclass(frozen=True, slots=True)
class InternalRedirectDTO:
    uri: str


class DownloadDeliveryProvider(Protocol):
    def internal_redirect(self, key: StorageKey) -> InternalRedirectDTO | None:
        """Return an internal proxy URI, or None for application streaming."""
        ...


@dataclass(frozen=True, slots=True)
class DownloadMetricDTO:
    outcome: str
    duration_seconds: float
    bytes_sent: int
    average_bytes_per_second: float


class DownloadMetricsRecorder(Protocol):
    def record(self, metric: DownloadMetricDTO) -> None:
        """Record completion or client cancellation."""
        ...
