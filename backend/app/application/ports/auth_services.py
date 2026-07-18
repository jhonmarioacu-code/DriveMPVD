"""Cryptographic and time ports used by authentication use cases."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dtos.auth import (
    AccessTokenClaimsDTO,
    IssuedTokenDTO,
    PasswordVerificationDTO,
    RefreshTokenClaimsDTO,
)


class Clock(Protocol):
    """Provide timezone-aware UTC instants."""

    def now(self) -> datetime:
        """Return the current instant."""
        ...


class PasswordHasher(Protocol):
    """Argon2id password hashing boundary."""

    def hash(self, password: str) -> str:
        """Hash a password using the active policy."""
        ...

    def verify(self, password_hash: str, password: str) -> PasswordVerificationDTO:
        """Verify without raising for a mismatch."""
        ...

    def verify_dummy(self, password: str) -> None:
        """Perform equivalent work when no account exists."""
        ...


class JwtProvider(Protocol):
    """Issue and validate fixed-algorithm access and refresh JWTs."""

    def issue_access(
        self,
        *,
        admin_id: UUID,
        session_id: UUID,
        jti: UUID,
        now: datetime,
    ) -> IssuedTokenDTO:
        """Issue a short-lived access JWT."""
        ...

    def issue_refresh(
        self,
        *,
        admin_id: UUID,
        session_id: UUID,
        family_id: UUID,
        jti: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> IssuedTokenDTO:
        """Issue a refresh JWT for an existing session family."""
        ...

    def decode_access(self, token: str, *, now: datetime) -> AccessTokenClaimsDTO:
        """Validate signature, type, audience, issuer and temporal claims."""
        ...

    def decode_refresh(self, token: str, *, now: datetime) -> RefreshTokenClaimsDTO:
        """Validate a refresh JWT and its family/session claims."""
        ...


class SecretTokenProvider(Protocol):
    """Generate and compare non-password secrets and fingerprints."""

    def generate(self) -> str:
        """Return a cryptographically random URL-safe token."""
        ...

    def digest(self, value: str) -> str:
        """Return a keyed, fixed-length digest."""
        ...

    def matches(self, value: str, expected_digest: str) -> bool:
        """Compare a secret to its digest in constant time."""
        ...

    def fingerprint(self, value: str) -> str:
        """Pseudonymize request metadata for audit/rate limiting."""
        ...
