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

    async def async_lookup_by_id(self, mbid: str) -> ExternalMetadata | None:
        """Fetch full release metadata and album art.

        Args:
            mbid: MusicBrainz release ID.

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
        tracks = self._extract_tracks(release)

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

    def _extract_tracks(self, release: dict[str, Any]) -> list[TrackMetadata]:
        """Extract track metadata from release data."""
        tracks: list[TrackMetadata] = []

        medium_list = release.get("medium-list", [])
        if not medium_list:
            return tracks

        for medium in medium_list:
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
