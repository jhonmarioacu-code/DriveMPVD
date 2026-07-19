"""Current ASGI delivery policy and structured download metrics."""

import logging

from app.application.ports.download_services import (
    DownloadMetricDTO,
    InternalRedirectDTO,
)
from app.application.ports.file_storage import StorageKey

logger = logging.getLogger("drivempvd.download.metrics")


class ApplicationStreamDeliveryProvider:
    """Select application streaming; replaceable by an X-Accel adapter."""

    def internal_redirect(self, key: StorageKey) -> InternalRedirectDTO | None:
        del key
        return None


class LoggingDownloadMetricsRecorder:
    def record(self, metric: DownloadMetricDTO) -> None:
        logger.info(
            "download_metric",
            extra={
                "outcome": metric.outcome,
                "duration_seconds": metric.duration_seconds,
                "bytes_sent": metric.bytes_sent,
                "average_bytes_per_second": metric.average_bytes_per_second,
            },
        )
