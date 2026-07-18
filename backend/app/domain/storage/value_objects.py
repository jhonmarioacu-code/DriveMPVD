"""Validated storage value objects."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePath
from typing import Final

from app.domain.storage.exceptions import InvalidChecksumError, InvalidEntryNameError

_SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class EntryName:
    """Visible name and collision key independent of physical storage."""

    value: str
    normalized: str

    @classmethod
    def create(cls, value: str) -> "EntryName":
        visible = unicodedata.normalize("NFC", value).strip()
        normalized = unicodedata.normalize("NFKC", visible).casefold()
        if (
            not visible
            or len(visible) > 255
            or visible in {".", ".."}
            or "/" in visible
            or "\\" in visible
            or "\x00" in visible
            or any(
                unicodedata.category(character).startswith("C") for character in visible
            )
        ):
            raise InvalidEntryNameError()
        return cls(value=visible, normalized=normalized)

    @property
    def extension(self) -> str:
        """Return normalized suffix without a leading dot."""
        suffix = PurePath(self.value).suffix
        return suffix[1:].casefold() if suffix else ""


@dataclass(frozen=True, slots=True)
class Sha256Checksum:
    """Canonical lowercase SHA-256 hex digest."""

    value: str

    @classmethod
    def create(cls, value: str) -> "Sha256Checksum":
        normalized = value.casefold()
        if _SHA256_PATTERN.fullmatch(normalized) is None:
            raise InvalidChecksumError()
        return cls(normalized)
