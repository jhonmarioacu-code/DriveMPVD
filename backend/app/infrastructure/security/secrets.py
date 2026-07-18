"""Keyed secret digests, fingerprints and CSRF token generation."""

import hashlib
import hmac
import secrets

from app.infrastructure.config import Settings


class HmacSecretTokenProvider:
    """Use independent HMAC domains for secrets and privacy fingerprints."""

    def __init__(self, settings: Settings) -> None:
        self._key = settings.auth_secret_pepper.get_secret_value().encode()

    def generate(self) -> str:
        return secrets.token_urlsafe(32)

    def digest(self, value: str) -> str:
        return self._hmac(b"secret\x00" + value.encode())

    def matches(self, value: str, expected_digest: str) -> bool:
        return hmac.compare_digest(self.digest(value), expected_digest)

    def fingerprint(self, value: str) -> str:
        return self._hmac(b"fingerprint\x00" + value.encode())

    def _hmac(self, value: bytes) -> str:
        return hmac.new(self._key, value, hashlib.sha256).hexdigest()
