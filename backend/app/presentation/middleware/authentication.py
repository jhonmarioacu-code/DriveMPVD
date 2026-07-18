"""ASGI authentication middleware injected with an application use case."""

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.application.exceptions import ApplicationError
from app.application.use_cases.auth import AuthenticateAccessUseCase


class AuthenticationMiddleware:
    """Resolve Bearer/cookie credentials without importing domain or persistence."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        authenticate: AuthenticateAccessUseCase,
        access_cookie_name: str,
        csrf_cookie_name: str,
        csrf_header_name: str,
        csrf_exempt_paths: frozenset[str],
    ) -> None:
        self._app = app
        self._authenticate = authenticate
        self._access_cookie_name = access_cookie_name
        self._csrf_cookie_name = csrf_cookie_name
        self._csrf_header_name = csrf_header_name
        self._csrf_exempt_paths = csrf_exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        bearer_token = self._bearer_token(headers.get("authorization"))
        cookies = self._cookies(headers.get("cookie", ""))
        cookie_token = cookies.get(self._access_cookie_name)
        token = bearer_token or cookie_token
        state = scope.setdefault("state", {})
        state["principal"] = None
        state["auth_error"] = None
        if token is not None:
            via_cookie = bearer_token is None and cookie_token is not None
            require_csrf = (
                via_cookie
                and scope["method"] not in {"GET", "HEAD", "OPTIONS"}
                and scope["path"] not in self._csrf_exempt_paths
            )
            try:
                state["principal"] = await self._authenticate.execute(
                    token,
                    authenticated_via_cookie=via_cookie,
                    require_csrf=require_csrf,
                    csrf_cookie=cookies.get(self._csrf_cookie_name),
                    csrf_header=headers.get(self._csrf_header_name),
                )
            except ApplicationError as exc:
                state["auth_error"] = exc
        await self._app(scope, receive, send)

    @staticmethod
    def _bearer_token(value: str | None) -> str | None:
        if value is None:
            return None
        scheme, separator, token = value.partition(" ")
        if separator and scheme.casefold() == "bearer" and token:
            return token
        return None

    @staticmethod
    def _cookies(value: str) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for item in value.split(";"):
            name, separator, cookie_value = item.strip().partition("=")
            if separator:
                cookies[name] = cookie_value
        return cookies
