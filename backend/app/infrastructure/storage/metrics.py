"""Structured logging adapter for upload metrics."""

import logging

from app.application.ports.upload_services import UploadMetricDTO

logger = logging.getLogger("drivempvd.upload.metrics")


class LoggingUploadMetricsRecorder:
    def record(self, metric: UploadMetricDTO) -> None:
        logger.info(
            "upload_metric",
            extra={
                "operation": metric.operation,
                "outcome": metric.outcome,
                "duration_seconds": metric.duration_seconds,
                "size_bytes": metric.size_bytes,
                "average_bytes_per_second": metric.average_bytes_per_second,
                "error_code": metric.error_code,
            },
        )
