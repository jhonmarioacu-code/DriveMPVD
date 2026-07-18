"""Stable authentication domain enumerations."""

from enum import StrEnum


class SecurityEventType(StrEnum):
    """Security-relevant actions retained for audit."""

    ADMIN_CREATED = "admin.created"
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    REFRESH_ROTATED = "auth.refresh_rotated"
    REFRESH_REUSE_DETECTED = "auth.refresh_reuse_detected"
    SESSION_REVOKED = "auth.session_revoked"
    ALL_SESSIONS_REVOKED = "auth.all_sessions_revoked"


class SessionRevocationReason(StrEnum):
    """Reason an authentication session became unusable."""

    LOGOUT = "logout"
    REFRESH_REUSE = "refresh_reuse"
    ADMIN_ACTION = "admin_action"
    PASSWORD_CHANGED = "password_changed"
