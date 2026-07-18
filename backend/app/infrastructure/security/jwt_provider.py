"""Fixed-algorithm PyJWT access and refresh token adapter."""

from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

import jwt
from jwt import PyJWTError

from app.application.dtos.auth import (
    AccessTokenClaimsDTO,
    IssuedTokenDTO,
    RefreshTokenClaimsDTO,
)
from app.application.exceptions import AuthenticationError
from app.infrastructure.config import Settings

_ALGORITHM: Final[str] = "HS256"


class PyJwtProvider:
    """Issue and validate JWTs without trusting header-selected algorithms."""

    def __init__(self, settings: Settings) -> None:
        self._access_secret = settings.jwt_access_secret.get_secret_value()
        self._refresh_secret = settings.jwt_refresh_secret.get_secret_value()
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._access_ttl = timedelta(seconds=settings.access_token_ttl_seconds)

    def issue_access(
        self,
        *,
        admin_id: UUID,
        session_id: UUID,
        jti: UUID,
        now: datetime,
    ) -> IssuedTokenDTO:
        expires_at = now + self._access_ttl
        token = self._encode(
            secret=self._access_secret,
            token_type="access",
            admin_id=admin_id,
            session_id=session_id,
            jti=jti,
            now=now,
            expires_at=expires_at,
        )
        return IssuedTokenDTO(value=token, expires_at=expires_at)

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
        token = self._encode(
            secret=self._refresh_secret,
            token_type="refresh",
            admin_id=admin_id,
            session_id=session_id,
            family_id=family_id,
            jti=jti,
            now=now,
            expires_at=expires_at,
        )
        return IssuedTokenDTO(value=token, expires_at=expires_at)

    def decode_access(self, token: str, *, now: datetime) -> AccessTokenClaimsDTO:
        payload = self._decode(
            token,
            secret=self._access_secret,
            expected_type="access",
            now=now,
        )
        try:
            claims = AccessTokenClaimsDTO(
                admin_id=UUID(payload["sub"]),
                session_id=UUID(payload["sid"]),
                jti=UUID(payload["jti"]),
                issued_at=self._instant(payload["iat"]),
                expires_at=self._instant(payload["exp"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError() from exc
        self._validate_time(claims.issued_at, claims.expires_at, now)
        return claims

    def decode_refresh(self, token: str, *, now: datetime) -> RefreshTokenClaimsDTO:
        payload = self._decode(
            token,
            secret=self._refresh_secret,
            expected_type="refresh",
            now=now,
        )
        try:
            claims = RefreshTokenClaimsDTO(
                admin_id=UUID(payload["sub"]),
                session_id=UUID(payload["sid"]),
                family_id=UUID(payload["fid"]),
                jti=UUID(payload["jti"]),
                issued_at=self._instant(payload["iat"]),
                expires_at=self._instant(payload["exp"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError() from exc
        self._validate_time(claims.issued_at, claims.expires_at, now)
        return claims

    def _encode(
        self,
        *,
        secret: str,
        token_type: str,
        admin_id: UUID,
        session_id: UUID,
        jti: UUID,
        now: datetime,
        expires_at: datetime,
        family_id: UUID | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": str(admin_id),
            "sid": str(session_id),
            "jti": str(jti),
            "type": token_type,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        if family_id is not None:
            payload["fid"] = str(family_id)
        return jwt.encode(payload, secret, algorithm=_ALGORITHM)

    def _decode(
        self,
        token: str,
        *,
        secret: str,
        expected_type: str,
        now: datetime,
    ) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "sid",
                        "jti",
                        "type",
                        "iat",
                        "nbf",
                        "exp",
                    ],
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
        except PyJWTError as exc:
            raise AuthenticationError() from exc
        if payload.get("type") != expected_type:
            raise AuthenticationError()
        try:
            not_before = self._instant(payload["nbf"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError() from exc
        if not_before > now + timedelta(seconds=30):
            raise AuthenticationError()
        return payload

    @staticmethod
    def _instant(value: object) -> datetime:
        if not isinstance(value, int):
            raise ValueError
        return datetime.fromtimestamp(value, tz=UTC)

    @staticmethod
    def _validate_time(
        issued_at: datetime, expires_at: datetime, now: datetime
    ) -> None:
        if expires_at <= now or issued_at > now + timedelta(seconds=30):
            raise AuthenticationError()
