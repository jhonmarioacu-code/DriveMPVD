"""Streaming upload inspection and metrics boundaries."""

from dataclasses import dataclass
from typing import Protocol


class MimeDetector(Protocol):
    def detect(self, prefix: bytes, *, filename: str) -> str:
        """Detect a conservative MIME type from a bounded content prefix."""
        ...


@dataclass(frozen=True, slots=True)
class UploadMetricDTO:
    operation: str
    outcome: str
    duration_seconds: float
    size_bytes: int
    average_bytes_per_second: float
    error_code: str | None = None


class UploadMetricsRecorder(Protocol):
    def record(self, metric: UploadMetricDTO) -> None:
        """Record one bounded upload operation metric."""
        ...
