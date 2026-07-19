"""JSON logging implemented with the Python standard library."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Final

from app.infrastructure.config.settings import Settings

_EXTRA_FIELDS: Final[tuple[str, ...]] = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "error_code",
    "operation",
    "outcome",
    "duration_seconds",
    "size_bytes",
    "average_bytes_per_second",
    "bytes_sent",
)


class JsonFormatter(logging.Formatter):
    """Serialize predictable, non-secret log fields as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON line suitable for container log collectors."""
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    """Configure the root logger for structured stdout output."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)
