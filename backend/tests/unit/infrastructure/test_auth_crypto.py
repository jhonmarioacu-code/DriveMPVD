from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.application.exceptions import AuthenticationError
from app.infrastructure.config.settings import AppEnvironment, Settings
from app.infrastructure.persistence.identifiers import Uuid7Generator
from app.infrastructure.security import (
    Argon2idPasswordHasher,
    HmacSecretTokenProvider,
    PyJwtProvider,
)


def _settings(*, access_token_ttl_seconds: int = 900) -> Settings:
    return Settings(
        environment=AppEnvironment.TEST,
        storage_root=Path.cwd().anchor,
        argon2_time_cost=1,
        argon2_memory_cost_kib=19_456,
        argon2_parallelism=1,
        jwt_access_secret="a" * 40,
        jwt_refresh_secret="b" * 40,
        auth_secret_pepper="c" * 40,
        access_token_ttl_seconds=access_token_ttl_seconds,
    )


def test_argon2id_hash_verify_mismatch_and_dummy_path() -> None:
    hasher = Argon2idPasswordHasher(_settings())
    encoded = hasher.hash("correct horse battery staple")

    assert encoded.startswith("$argon2id$")
    assert hasher.verify(encoded, "correct horse battery staple").valid
    assert not hasher.verify(encoded, "wrong").valid
    assert not hasher.verify("invalid", "wrong").valid
    hasher.verify_dummy("unknown account password")


def test_hmac_secrets_are_random_domain_separated_and_constant_time() -> None:
    provider = HmacSecretTokenProvider(_settings())
    first = provider.generate()
    second = provider.generate()

    assert first != second
    assert provider.matches(first, provider.digest(first))
    assert not provider.matches(second, provider.digest(first))
    assert provider.digest("same") != provider.fingerprint("same")


def test_jwt_access_and_refresh_round_trip_and_type_separation() -> None:
    provider = PyJwtProvider(_settings(access_token_ttl_seconds=120))
    generator = Uuid7Generator()
    now = datetime.now(UTC).replace(microsecond=0)
    admin_id = generator.new()
    session_id = generator.new()
    family_id = generator.new()
    access_jti = generator.new()
    refresh_jti = generator.new()

    access = provider.issue_access(
        admin_id=admin_id,
        session_id=session_id,
        jti=access_jti,
        now=now,
    )
    refresh = provider.issue_refresh(
        admin_id=admin_id,
        session_id=session_id,
        family_id=family_id,
        jti=refresh_jti,
        now=now,
        expires_at=now + timedelta(days=1),
    )

    access_claims = provider.decode_access(access.value, now=now)
    refresh_claims = provider.decode_refresh(refresh.value, now=now)
    assert access_claims.jti == access_jti
    assert refresh_claims.family_id == family_id

    with pytest.raises(AuthenticationError):
        provider.decode_access(refresh.value, now=now)
    with pytest.raises(AuthenticationError):
        provider.decode_refresh(access.value, now=now)
    with pytest.raises(AuthenticationError):
        provider.decode_access(access.value + "tampered", now=now)
    with pytest.raises(AuthenticationError):
        provider.decode_access(access.value, now=now + timedelta(minutes=3))
