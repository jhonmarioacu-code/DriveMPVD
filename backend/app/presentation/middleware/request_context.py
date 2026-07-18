"""Request correlation and structured access logging middleware."""

import logging
import re
from time import perf_counter
from typing import Final
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """Add a safe request id and emit one structured access log per request."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        incoming_id = headers.get("x-request-id", "")
        request_id = (
            incoming_id if _REQUEST_ID_PATTERN.fullmatch(incoming_id) else str(uuid4())
        )
        scope.setdefault("state", {})["request_id"] = request_id
        status_code = status_unknown = 0
        started_at = perf_counter()

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_context)
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 3)
            logger.info(
                "http_request_completed",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code or status_unknown,
                    "duration_ms": duration_ms,
                },
            )
