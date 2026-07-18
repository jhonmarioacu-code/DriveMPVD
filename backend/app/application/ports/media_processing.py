"""Future streaming media/security processing interfaces."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from app.shared.json_types import JsonObject


@dataclass(frozen=True, slots=True)
class ExtractedMetadataDTO:
    mime_type: str
    attributes: JsonObject


@dataclass(frozen=True, slots=True)
class GeneratedAssetDTO:
    mime_type: str
    chunks: AsyncIterator[bytes]


@dataclass(frozen=True, slots=True)
class VirusScanResultDTO:
    clean: bool
    threat_name: str | None = None


class ThumbnailGenerator(Protocol):
    async def generate(
        self,
        chunks: AsyncIterator[bytes],
        *,
        mime_type: str,
        variant: str,
    ) -> GeneratedAssetDTO: ...


class PreviewGenerator(Protocol):
    async def generate(
        self,
        chunks: AsyncIterator[bytes],
        *,
        mime_type: str,
        variant: str,
    ) -> GeneratedAssetDTO: ...


class MetadataExtractor(Protocol):
    async def extract(
        self,
        chunks: AsyncIterator[bytes],
        *,
        declared_mime_type: str | None,
    ) -> ExtractedMetadataDTO: ...


class VirusScanner(Protocol):
    async def scan(self, chunks: AsyncIterator[bytes]) -> VirusScanResultDTO: ...
