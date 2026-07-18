from datetime import UTC, datetime, timedelta

from app.domain.auth.entities import AdminAccount, AuthSession
from app.domain.auth.enums import SessionRevocationReason
from app.infrastructure.persistence.identifiers import Uuid7Generator


def _account(now: datetime) -> AdminAccount:
    return AdminAccount(
        id=Uuid7Generator().new(),
        username="admin",
        normalized_username="admin",
        password_hash="hash",
        enabled=True,
        failed_login_attempts=0,
        locked_until=None,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def test_account_locks_at_threshold_and_success_resets_state() -> None:
    now = datetime.now(UTC)
    account = _account(now)

    account.register_failed_login(
        now=now,
        maximum_attempts=2,
        lock_duration=timedelta(minutes=5),
    )
    assert not account.is_locked(now)
    account.register_failed_login(
        now=now,
        maximum_attempts=2,
        lock_duration=timedelta(minutes=5),
    )
    assert account.is_locked(now)

    account.register_successful_login(now + timedelta(minutes=6))

    assert account.failed_login_attempts == 0
    assert account.locked_until is None
    assert account.last_login_at == now + timedelta(minutes=6)


def test_session_rotation_activity_and_idempotent_revocation() -> None:
    now = datetime.now(UTC)
    generator = Uuid7Generator()
    session = AuthSession(
        id=generator.new(),
        admin_id=generator.new(),
        family_id=generator.new(),
        refresh_jti=generator.new(),
        refresh_token_hash="old",
        csrf_token_hash="csrf-old",
        expires_at=now + timedelta(days=1),
        last_rotated_at=now,
        revoked_at=None,
        revoke_reason=None,
        ip_hash="ip",
        user_agent_hash="ua",
        created_at=now,
        updated_at=now,
    )
    new_jti = generator.new()
    rotated_at = now + timedelta(minutes=1)

    assert session.is_active(now)
    session.rotate(
        refresh_jti=new_jti,
        refresh_token_hash="new",
        csrf_token_hash="csrf-new",
        now=rotated_at,
    )
    session.revoke(now=rotated_at, reason=SessionRevocationReason.LOGOUT)
    session.revoke(
        now=rotated_at + timedelta(minutes=1),
        reason=SessionRevocationReason.ADMIN_ACTION,
    )

    assert session.refresh_jti == new_jti
    assert session.refresh_token_hash == "new"
    assert not session.is_active(rotated_at)
    assert session.revoke_reason is SessionRevocationReason.LOGOUT
    assert session.revoked_at == rotated_at
