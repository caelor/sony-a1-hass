"""Fingerprint computation for disc identification."""

from __future__ import annotations

from typing import Any

SECTORS_PER_SECOND = 75
CD_PREGAP_SECTORS = 150


def compute_fingerprint(toc: list[dict[str, Any]], total_seconds: int) -> str:
    """Compute a deterministic fingerprint string from TOC data.

    Args:
        toc: List of track dicts with 'length' key (seconds).
        total_seconds: Total disc length in seconds.

    Returns:
        Fingerprint string: "total_seconds:track_count:len1,len2,..."
    """
    track_lengths = ",".join(str(t["length"]) for t in toc)
    return f"{total_seconds}:{len(toc)}:{track_lengths}"


def build_toc_string(toc: list[dict[str, Any]], total_seconds: int) -> str:
    """Convert TOC to MusicBrainz TOC format.

    Converts track lengths in seconds to sector offsets.
    Track 1 starts at sector 150 (standard CD pregap).
    Each subsequent track starts where the previous one ended.
    Leadout is derived from track lengths for consistency.

    Args:
        toc: List of track dicts with 'length' key (seconds).
        total_seconds: Total disc length in seconds (unused, kept for interface compatibility).

    Returns:
        TOC string: "1 {track_count} {leadout_sectors} {offset1} {offset2} ..."
    """
    track_count = len(toc)

    offsets: list[int] = []
    current_offset = CD_PREGAP_SECTORS

    for track in toc:
        offsets.append(current_offset)
        current_offset += track["length"] * SECTORS_PER_SECOND

    leadout_sectors = current_offset
    offset_str = " ".join(str(o) for o in offsets)
    return f"1 {track_count} {leadout_sectors} {offset_str}"
