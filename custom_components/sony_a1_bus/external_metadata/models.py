"""Data models for external metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrackMetadata:
    """Metadata for a single track."""

    title: str
    artist: str
    recording_id: str


@dataclass(frozen=True)
class ExternalMetadata:
    """Metadata for a disc from an external source."""

    source: str
    source_id: str
    album_title: str
    artist: str
    tracks: list[TrackMetadata]
    album_art_url: str | None
