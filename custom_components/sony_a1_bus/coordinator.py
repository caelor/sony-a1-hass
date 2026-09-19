"""Coordinator for external metadata lookups."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .external_metadata import MetadataCache, MetadataProvider
from .external_metadata.fingerprint import compute_fingerprint
from .external_metadata.musicbrainz import SOURCE_NAME, MusicBrainzProvider

if TYPE_CHECKING:
    from .devices.player import Player

_LOGGER = logging.getLogger(__name__)


class MetadataCoordinator:
    """Coordinates external metadata lookups across providers.

    Manages the cache, providers, and lookup lifecycle.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._hass = hass
        self._entry = entry
        self._cache = MetadataCache(hass)
        self._providers: dict[str, MetadataProvider] = {
            SOURCE_NAME: MusicBrainzProvider(hass),
        }

    async def async_setup(self) -> None:
        """Load persistent cache."""
        await self._cache.async_load()

    @property
    def cache(self) -> MetadataCache:
        """Return the metadata cache."""
        return self._cache

    async def async_on_toc_complete(self, player: Player) -> None:
        """Handle TOC completion by performing metadata lookup.

        Called when a player's TOC is fully populated.

        Args:
            player: The player whose TOC is complete.
        """
        if not self.is_enabled(player):
            _LOGGER.debug("Metadata lookup disabled for %s", player.name)
            return

        total_seconds = player.total_minutes * 60 + player.total_seconds
        fingerprint = compute_fingerprint(player.toc, total_seconds)

        cached = self._cache.get_source_id(fingerprint)

        if cached:
            source_name, source_id = cached.split(":", 1)
            _LOGGER.debug(
                "Using cached source_id %s for fingerprint %s",
                cached,
                fingerprint,
            )
        else:
            source_name, source_id = await self._async_find_source_id(
                player, fingerprint
            )
            if source_id is None:
                _LOGGER.debug("No metadata found for fingerprint %s", fingerprint)
                return

            self._cache.set_source_id(fingerprint, f"{source_name}:{source_id}")
            await self._cache.async_save()

        metadata = await self._providers[source_name].async_lookup_by_id(source_id, player.toc)

        if player.toc:
            player.external_metadata = metadata
            player._notify_entities()
            if metadata:
                _LOGGER.debug(
                    "Loaded metadata for %s: %s - %s",
                    player.name,
                    metadata.artist,
                    metadata.album_title,
                )

    async def _async_find_source_id(
        self, player: Player, fingerprint: str
    ) -> tuple[str, str | None]:
        """Try each provider to find a source_id for the fingerprint.

        Returns:
            Tuple of (source_name, source_id). source_id is None if not found.
        """
        total_seconds = player.total_minutes * 60 + player.total_seconds

        for name, provider in self._providers.items():
            source_id = await provider.async_lookup(fingerprint, player.toc, total_seconds)
            if source_id is not None:
                return name, source_id

        return SOURCE_NAME, None

    async def async_set_musicbrainz_id(self, player: Player, mbid: str) -> None:
        """Override the MusicBrainz ID for the current disc.

        Saves the override to cache and triggers a metadata reload.

        Args:
            player: The player with the loaded disc.
            mbid: The correct MusicBrainz release ID.
        """
        if not player.toc:
            _LOGGER.warning("Cannot set MBID: no TOC loaded for %s", player.name)
            return

        total_seconds = player.total_minutes * 60 + player.total_seconds
        fingerprint = compute_fingerprint(player.toc, total_seconds)

        self._cache.set_source_id(fingerprint, f"{SOURCE_NAME}:{mbid}")
        await self._cache.async_save()

        player.external_metadata = None
        await self.async_on_toc_complete(player)

    def is_enabled(self, player: Player) -> bool:
        """Check if metadata lookup is enabled for a player."""
        return self._cache.get_enabled(player.unique_id)

    def set_enabled(self, player: Player, enabled: bool) -> None:
        """Set whether metadata lookup is enabled for a player."""
        self._cache.set_enabled(player.unique_id, enabled)
