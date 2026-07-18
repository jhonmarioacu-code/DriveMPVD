"""HTTP authentication helpers with no domain or infrastructure dependency."""

from dataclasses import dataclass

from fastapi import Request

from app.application.dtos.auth import AdminPrincipalDTO
from app.application.exceptions import AuthenticationRequiredError


@dataclass(frozen=True, slots=True)
class AuthCookiePolicy:
    """Cookie attributes injected from centralized infrastructure settings."""

    secure: bool
    domain: str | None
    access_name: str
    refresh_name: str
    csrf_name: str
    csrf_header_name: str
    access_max_age: int
    refresh_max_age: int
    refresh_path: str


def require_principal(request: Request) -> AdminPrincipalDTO:
    """Return middleware-authenticated principal or raise a uniform error."""
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, AdminPrincipalDTO):
        return principal
    auth_error = getattr(request.state, "auth_error", None)
    if isinstance(auth_error, Exception):
        raise auth_error
    raise AuthenticationRequiredError()


def request_metadata(request: Request) -> tuple[str, str]:
    """Return bounded raw metadata; persistence receives only keyed fingerprints."""
    client_ip = request.client.host if request.client is not None else "unknown"
    user_agent = request.headers.get("user-agent", "")[:512]
    return client_ip, user_agent
