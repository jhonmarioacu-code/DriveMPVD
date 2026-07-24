"""Authentication use-case DTOs independent of HTTP and persistence."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PasswordVerificationDTO:
    """Result of Argon2id verification and policy freshness check."""

    valid: bool
    needs_rehash: bool


@dataclass(frozen=True, slots=True)
class AccessTokenClaimsDTO:
    """Validated access JWT claims."""

    admin_id: UUID
    session_id: UUID
    jti: UUID
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshTokenClaimsDTO:
    """Validated refresh JWT claims."""

    admin_id: UUID
    session_id: UUID
    family_id: UUID
    jti: UUID
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class IssuedTokenDTO:
    """Encoded JWT and its expiry."""

    value: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthenticationResultDTO:
    """Tokens and CSRF secret produced by login or rotation."""

    access_token: IssuedTokenDTO
    refresh_token: IssuedTokenDTO
    csrf_token: str
    session_id: UUID


@dataclass(frozen=True, slots=True)
class AdminPrincipalDTO:
    """Authenticated singleton administrator context."""

    admin_id: UUID
    session_id: UUID
    username: str
    authenticated_via_cookie: bool


@dataclass(frozen=True, slots=True)
class LoginCommandDTO:
    """Credential login input with request fingerprints."""

    username: str
    password: str
    client_ip: str
    user_agent: str


@dataclass(frozen=True, slots=True)
class RefreshCommandDTO:
    """Refresh input and optional cookie CSRF proof."""

    refresh_token: str
    client_ip: str
    user_agent: str
    csrf_cookie: str | None
    csrf_header: str | None
    used_cookie: bool


@dataclass(frozen=True, slots=True)
class BootstrapAdminCommandDTO:
    """Non-HTTP initial administrator creation input."""

    username: str
    password: str


@dataclass(frozen=True, slots=True)
class ChangeAdminPasswordCommandDTO:
    """Local administrative credential rotation input."""

    username: str
    password: str


@dataclass(frozen=True, slots=True)
class RateLimitDecisionDTO:
    """Atomic rate-limit outcome."""

    allowed: bool
    retry_after_seconds: int


@dataclass(frozen=True, slots=True)
class AuthPolicyDTO:
    """Validated authentication policy injected from centralized Settings."""

    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    maximum_failed_logins: int
    account_lock_seconds: int
    login_rate_limit: int
    login_rate_window_seconds: int
    login_rate_block_seconds: int
    refresh_rate_limit: int
    refresh_rate_window_seconds: int
    refresh_rate_block_seconds: int
    minimum_password_length: int
