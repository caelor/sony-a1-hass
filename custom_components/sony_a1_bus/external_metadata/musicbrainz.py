"""MusicBrainz metadata provider."""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

import aiohttp
import musicbrainzngs
from homeassistant.core import HomeAssistant

from .fingerprint import build_toc_string
from .models import ExternalMetadata, TrackMetadata

_LOGGER = logging.getLogger(__name__)

SOURCE_NAME = "musicbrainz"
CAA_BASE_URL = "https://coverartarchive.org"


def _calculate_offset_distance(our_offsets: list[int], their_offsets: list[int]) -> int:
    """Calculate sum of absolute differences between two offset lists.

    Args:
        our_offsets: Our track offsets (including pregap).
        their_offsets: Their track offsets from MusicBrainz.

    Returns:
        Sum of absolute differences in sectors. Lower is better.
    """
    if len(our_offsets) != len(their_offsets):
        return float("inf")
    return sum(abs(a - b) for a, b in zip(our_offsets, their_offsets))


class MusicBrainzProvider:
    """MusicBrainz metadata provider using musicbrainzngs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the provider."""
        self._hass = hass
        musicbrainzngs.set_useragent(
            "sony-a1-hass",
            "0.1",
            "https://github.com/caelor/sony-a1-hass",
        )

    async def async_lookup(
        self,
        fingerprint: str,
        toc: list[dict[str, Any]],
        total_seconds: int,
    ) -> str | None:
        """Perform fuzzy TOC search to find a MusicBrainz release.

        Args:
            fingerprint: Disc fingerprint (unused, for interface compatibility).
            toc: List of track dicts with 'length' key (seconds).
            total_seconds: Total disc length in seconds.

        Returns:
            MusicBrainz release ID (MBID) of first result, or None if no match.
        """
        toc_string = build_toc_string(toc, total_seconds)
        _LOGGER.debug("Looking up MusicBrainz release for TOC: %s", toc_string)

        try:
            result = await self._hass.async_add_executor_job(
                partial(
                    musicbrainzngs.get_releases_by_discid,
                    "-",
                    toc=toc_string,
                    includes=["recordings", "artist-credits"],
                    cdstubs=False,
                    media_format="all",
                )
            )
        except musicbrainzngs.ResponseError as ex:
            _LOGGER.debug("No MusicBrainz results for fingerprint %s: %s", fingerprint, ex)
            return None
        except musicbrainzngs.NetworkError as ex:
            _LOGGER.warning("MusicBrainz network error: %s", ex)
            return None

        release_list = result.get("release-list", [])
        if not release_list:
            _LOGGER.debug("No MusicBrainz releases found for fingerprint %s", fingerprint)
            return None

        our_offsets = self._extract_offsets_from_toc(toc)
        best_release = self._find_best_match(release_list, our_offsets)

        mbid = best_release["id"]
        _LOGGER.debug("MusicBrainz fuzzy search found release %s for fingerprint %s", mbid, fingerprint)
        return mbid

    def _extract_offsets_from_toc(self, toc: list[dict[str, Any]]) -> list[int]:
        """Extract sector offsets from TOC data.

        Args:
            toc: List of track dicts with 'length' key (seconds).

        Returns:
            List of sector offsets including pregap.
        """
        from .fingerprint import CD_PREGAP_SECTORS, SECTORS_PER_SECOND

        offsets: list[int] = []
        current_offset = CD_PREGAP_SECTORS

        for track in toc:
            offsets.append(current_offset)
            current_offset += track["length"] * SECTORS_PER_SECOND

        return offsets

    def _find_best_match(
        self, release_list: list[dict[str, Any]], our_offsets: list[int]
    ) -> dict[str, Any]:
        """Find the best matching release based on discid offset similarity.

        Args:
            release_list: List of release dicts from MusicBrainz.
            our_offsets: Our track offsets (including pregap).

        Returns:
            Best matching release dict.
        """
        candidates_with_discids: list[tuple[int, dict[str, Any]]] = []

        for release in release_list:
            for medium in release.get("medium-list", []):
                for disc in medium.get("disc-list", []):
                    disc_offsets = disc.get("offset-list", [])
                    if disc_offsets:
                        distance = _calculate_offset_distance(our_offsets, disc_offsets)
                        candidates_with_discids.append((distance, release))
                        break
                else:
                    continue
                break

        if candidates_with_discids:
            candidates_with_discids.sort(key=lambda x: x[0])
            best_distance, best_release = candidates_with_discids[0]
            _LOGGER.debug(
                "Best match has discid offset distance %d sectors", best_distance
            )
            return best_release

        _LOGGER.debug("No releases with discids found, using first result")
        return release_list[0]

    async def async_lookup_by_id(
        self, mbid: str, toc: list[dict[str, Any]] | None = None
    ) -> ExternalMetadata | None:
        """Fetch full release metadata and album art.

        Args:
            mbid: MusicBrainz release ID.
            toc: Optional TOC data for multi-disc matching.

        Returns:
            ExternalMetadata object, or None if lookup failed.
        """
        try:
            result = await self._hass.async_add_executor_job(
                partial(
                    musicbrainzngs.get_release_by_id,
                    mbid,
                    includes=["recordings", "artist-credits", "media"],
                )
            )
        except musicbrainzngs.ResponseError as ex:
            _LOGGER.warning("MusicBrainz lookup failed for %s: %s", mbid, ex)
            return None
        except musicbrainzngs.NetworkError as ex:
            _LOGGER.warning("MusicBrainz network error: %s", ex)
            return None

        release = result.get("release")
        if release is None:
            _LOGGER.warning("No release data in MusicBrainz response for %s", mbid)
            return None

        album_title = release.get("title", "Unknown Album")
        artist = self._extract_artist(release)
        tracks = self._extract_tracks(release, toc)

        album_art_url = await self._async_get_front_cover_url(mbid)

        return ExternalMetadata(
            source=SOURCE_NAME,
            source_id=mbid,
            album_title=album_title,
            artist=artist,
            tracks=tracks,
            album_art_url=album_art_url,
        )

    def _extract_artist(self, release: dict[str, Any]) -> str:
        """Extract artist name from release data."""
        artist_credit = release.get("artist-credit", [])
        if not artist_credit:
            return "Unknown Artist"

        parts: list[str] = []
        for credit in artist_credit:
            if isinstance(credit, str):
                parts.append(credit)
            elif isinstance(credit, dict):
                artist = credit.get("artist", {})
                name = artist.get("name", "")
                if name:
                    parts.append(name)
                joinphrase = credit.get("joinphrase", "")
                if joinphrase:
                    parts.append(joinphrase)

        return "".join(parts) if parts else "Unknown Artist"

    def _extract_tracks(
        self, release: dict[str, Any], toc: list[dict[str, Any]] | None = None
    ) -> list[TrackMetadata]:
        """Extract track metadata from release data.

        For multi-disc releases, matches the TOC against each medium to find
        the correct disc's tracks. Falls back to all tracks if no match found.

        Args:
            release: MusicBrainz release data.
            toc: Optional TOC data for multi-disc matching.

        Returns:
            List of TrackMetadata objects.
        """
        medium_list = release.get("medium-list", [])
        if not medium_list:
            return []

        if toc and len(medium_list) > 1:
            matched_medium = self._match_medium_to_toc(medium_list, toc)
            if matched_medium:
                _LOGGER.debug(
                    "Matched TOC to medium %s of %s",
                    matched_medium.get("position", "?"),
                    len(medium_list),
                )
                return self._extract_tracks_from_medium(matched_medium)

        all_tracks: list[TrackMetadata] = []
        for medium in medium_list:
            all_tracks.extend(self._extract_tracks_from_medium(medium))
        return all_tracks

    def _match_medium_to_toc(
        self, medium_list: list[dict[str, Any]], toc: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Find the medium that best matches the TOC.

        Args:
            medium_list: List of mediums from MusicBrainz.
            toc: TOC data with track lengths.

        Returns:
            Matching medium dict, or None if no match found.
        """
        toc_lengths = [t["length"] for t in toc]
        _LOGGER.debug("TOC lengths (seconds): %s", toc_lengths)
        
        best_match: dict[str, Any] | None = None
        best_distance = float("inf")

        for medium in medium_list:
            track_list = medium.get("track-list", [])
            _LOGGER.debug(
                "Medium %s has %d tracks (TOC has %d)",
                medium.get("position"), len(track_list), len(toc)
            )
            
            if len(track_list) != len(toc):
                _LOGGER.debug("Skipping medium %s: track count mismatch", medium.get("position"))
                continue

            distance = 0
            for i, track in enumerate(track_list):
                mb_length_ms = int(track.get("length", 0))
                mb_length_sec = mb_length_ms // 1000
                diff = abs(mb_length_sec - toc_lengths[i])
                distance += diff
                _LOGGER.debug(
                    "Track %d: MB=%dms (%ds), TOC=%ds, diff=%d",
                    i+1, mb_length_ms, mb_length_sec, toc_lengths[i], diff
                )

            _LOGGER.debug("Medium %s total distance: %d", medium.get("position"), distance)
            
            if distance < best_distance:
                best_distance = distance
                best_match = medium

        _LOGGER.debug("Best match distance: %d (threshold: 10)", best_distance)
        
        if best_match and best_distance < 10:
            _LOGGER.debug("Selected medium %s", best_match.get("position"))
            return best_match
        _LOGGER.debug("No medium matched within threshold")
        return None

    def _extract_tracks_from_medium(
        self, medium: dict[str, Any]
    ) -> list[TrackMetadata]:
        """Extract track metadata from a single medium.

        Args:
            medium: Medium dict from MusicBrainz.

        Returns:
            List of TrackMetadata objects.
        """
        tracks: list[TrackMetadata] = []
        track_list = medium.get("track-list", [])

        for track in track_list:
            recording = track.get("recording", {})
            title = recording.get("title") or track.get("title", "Unknown Track")
            recording_id = recording.get("id", "")

            artist_credit = recording.get("artist-credit") or track.get("artist-credit", [])
            artist = self._artist_credit_to_string(artist_credit)

            tracks.append(
                TrackMetadata(
                    title=title,
                    artist=artist,
                    recording_id=recording_id,
                )
            )

        return tracks

    def _artist_credit_to_string(self, artist_credit: list[dict[str, Any]]) -> str:
        """Convert artist-credit list to display string."""
        if not artist_credit:
            return "Unknown Artist"

        parts: list[str] = []
        for credit in artist_credit:
            if isinstance(credit, str):
                parts.append(credit)
            elif isinstance(credit, dict):
                artist = credit.get("artist", {})
                name = artist.get("name", "")
                if name:
                    parts.append(name)
                joinphrase = credit.get("joinphrase", "")
                if joinphrase:
                    parts.append(joinphrase)

        return "".join(parts) if parts else "Unknown Artist"

    async def _async_get_front_cover_url(self, mbid: str) -> str | None:
        """Fetch front cover image URL from Cover Art Archive.

        Follows the redirect to get the actual image URL.

        Args:
            mbid: MusicBrainz release ID.

        Returns:
            URL to front cover image, or None if not available.
        """
        url = f"{CAA_BASE_URL}/release/{mbid}/front"

        try:
            async with aiohttp.ClientSession() as session, session.get(url, allow_redirects=False) as resp:
                if resp.status in (301, 302, 307, 308):
                    return resp.headers.get("Location")
                if resp.status == 200:
                    return url
                _LOGGER.debug(
                    "Cover Art Archive returned %d for release %s",
                    resp.status,
                    mbid,
                )
                return None
        except aiohttp.ClientError as ex:
            _LOGGER.debug("Cover Art Archive request failed for %s: %s", mbid, ex)
            return None
