"""External metadata lookup for disc identification.

This module provides a framework for looking up disc metadata from external
sources (e.g., MusicBrainz, Discogs) based on TOC data.
"""

from __future__ import annotations

from typing import Any, Protocol

from .cache import MetadataCache
from .models import ExternalMetadata, TrackMetadata

__all__ = [
    "ExternalMetadata",
    "MetadataCache",
    "MetadataProvider",
    "TrackMetadata",
]


class MetadataProvider(Protocol):
    """Protocol for metadata source providers.

    Implementations provide metadata lookup from a specific source.
    """

    async def async_lookup(
        self,
        fingerprint: str,
        toc: list[dict[str, Any]],
        total_seconds: int,
    ) -> str | None:
        """Search for a disc by fingerprint and return a source-specific ID.

        Args:
            fingerprint: Deterministic fingerprint string from TOC data.
            toc: List of track dicts with 'length' key (seconds).
            total_seconds: Total disc length in seconds.

        Returns:
            Source-specific identifier (e.g., MBID for MusicBrainz), or None.
        """
        ...

    async def async_lookup_by_id(
        self, source_id: str, toc: list[dict[str, Any]] | None = None
    ) -> ExternalMetadata | None:
        """Fetch full metadata for a disc by its source-specific ID.

        Args:
            source_id: Source-specific identifier (e.g., MBID for MusicBrainz).
            toc: Optional TOC data for multi-disc matching.

        Returns:
            ExternalMetadata object, or None if lookup failed.
        """
        ...
