"""Argon2id password hashing adapter."""

from contextlib import suppress

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.application.dtos.auth import PasswordVerificationDTO
from app.infrastructure.config import Settings


class Argon2idPasswordHasher:
    """Hash passwords with explicit Argon2id production parameters."""

    def __init__(self, settings: Settings) -> None:
        self._hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash("drivempvd-dummy-password")

    def hash(self, password: str) -> str:
        """Create a salted Argon2id encoded hash."""
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> PasswordVerificationDTO:
        """Return a mismatch instead of leaking Argon2 parser exceptions."""
        try:
            valid = self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return PasswordVerificationDTO(valid=False, needs_rehash=False)
        return PasswordVerificationDTO(
            valid=valid,
            needs_rehash=valid and self._hasher.check_needs_rehash(password_hash),
        )

    def verify_dummy(self, password: str) -> None:
        """Burn one normal verification when the username is unknown."""
        with suppress(VerifyMismatchError):
            self._hasher.verify(self._dummy_hash, password)
