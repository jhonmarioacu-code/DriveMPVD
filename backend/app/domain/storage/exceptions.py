"""Storage domain invariant violations."""

from typing import ClassVar

from app.domain.exceptions import DomainError


class StorageDomainError(DomainError):
    code: ClassVar[str] = "storage.domain_error"


class InvalidEntryNameError(StorageDomainError):
    code = "storage.invalid_entry_name"
    default_message = "The entry name is invalid."


class InvalidMoveError(StorageDomainError):
    code = "storage.invalid_move"
    default_message = "The entry cannot be moved to that destination."


class InvalidChecksumError(StorageDomainError):
    code = "storage.invalid_checksum"
    default_message = "The SHA-256 checksum is invalid."


class InvalidStateTransitionError(StorageDomainError):
    code = "storage.invalid_state_transition"
    default_message = "The storage entity cannot perform that transition."
