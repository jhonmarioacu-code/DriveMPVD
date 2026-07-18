import json
import logging

from app.infrastructure.logging import JsonFormatter


def test_json_formatter_emits_structured_context() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="drivempvd.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="request_complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-123"
    record.status_code = 200

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "request_complete"
    assert payload["request_id"] == "request-123"
    assert payload["status_code"] == 200
    assert "timestamp" in payload
