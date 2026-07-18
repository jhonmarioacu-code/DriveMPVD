"""Exceptions describing expected application failures."""

from typing import ClassVar


class ApplicationError(Exception):
    """Base error for a failed use case."""

    code: ClassVar[str] = "application.error"
    default_message: ClassVar[str] = "The operation could not be completed."

    def __init__(self, message: str | None = None) -> None:
        self.public_message = message or self.default_message
        super().__init__(self.public_message)


class ResourceNotFoundError(ApplicationError):
    """Requested resource does not exist or is unavailable."""

    code = "application.resource_not_found"
    default_message = "The requested resource was not found."


class ConflictError(ApplicationError):
    """Requested change conflicts with current state."""

    code = "application.conflict"
    default_message = "The operation conflicts with the current state."


class ApplicationValidationError(ApplicationError):
    """Input is well formed but invalid for the use case."""

    code = "application.validation_error"
    default_message = "The operation contains invalid values."


class DependencyUnavailableError(ApplicationError):
    """A required external dependency cannot serve the use case."""

    code = "application.dependency_unavailable"
    default_message = "A required service is temporarily unavailable."


class AuthenticationError(ApplicationError):
    """Credentials or authentication proof are invalid."""

    code = "auth.invalid_credentials"
    default_message = "Authentication failed."


class AuthenticationRequiredError(ApplicationError):
    """A protected operation has no valid administrator principal."""

    code = "auth.authentication_required"
    default_message = "Authentication is required."


class CsrfValidationError(ApplicationError):
    """Cookie-authenticated mutation lacks valid CSRF proof."""

    code = "auth.csrf_validation_failed"
    default_message = "CSRF validation failed."


class AccountDisabledError(ApplicationError):
    """The singleton administrator account is disabled."""

    code = "auth.account_disabled"
    default_message = "The administrator account is disabled."


class RateLimitExceededError(ApplicationError):
    """A security-sensitive endpoint exceeded its configured rate."""

    code = "auth.rate_limit_exceeded"
    default_message = "Too many authentication attempts. Try again later."

    def __init__(self, *, retry_after_seconds: int) -> None:
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__()


class AccountTemporarilyLockedError(RateLimitExceededError):
    """Credential failures temporarily locked the administrator account."""

    code = "auth.account_temporarily_locked"


class SessionRevokedError(AuthenticationError):
    """The referenced session has expired or was revoked."""

    code = "auth.session_revoked"
    default_message = "The authentication session is no longer valid."
