"""Persistent cache for fingerprint to source ID mappings."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "sony_a1_bus_metadata"
STORAGE_VERSION = 1

DATA_FINGERPRINT_SOURCE_ID = "fingerprint_source_id"
DATA_ENABLED = "enabled"


class MetadataCache:
    """Persistent cache for external metadata lookups.

    Stores fingerprint → source_id mappings and per-player enabled state.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self._hass = hass
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self._fingerprint_source_id: dict[str, str] = {}
        self._enabled: dict[str, bool] = {}

    async def async_load(self) -> None:
        """Load cache from storage."""
        data = await self._store.async_load()
        if data is None:
            return

        self._fingerprint_source_id = data.get(DATA_FINGERPRINT_SOURCE_ID, {})
        self._enabled = data.get(DATA_ENABLED, {})

    async def async_save(self) -> None:
        """Save cache to storage."""
        data = {
            DATA_FINGERPRINT_SOURCE_ID: self._fingerprint_source_id,
            DATA_ENABLED: self._enabled,
        }
        await self._store.async_save(data)

    def get_source_id(self, fingerprint: str) -> str | None:
        """Get cached source_id for a fingerprint.

        Args:
            fingerprint: Disc fingerprint string.

        Returns:
            Source ID string (e.g., "musicbrainz:<mbid>") or None if not cached.
        """
        return self._fingerprint_source_id.get(fingerprint)

    def set_source_id(self, fingerprint: str, source_id: str) -> None:
        """Cache a source_id for a fingerprint.

        Args:
            fingerprint: Disc fingerprint string.
            source_id: Source ID string (e.g., "musicbrainz:<mbid>").
        """
        self._fingerprint_source_id[fingerprint] = source_id

    def get_enabled(self, player_unique_id: str) -> bool:
        """Get whether metadata lookup is enabled for a player.

        Defaults to True if not explicitly set.

        Args:
            player_unique_id: Player's unique identifier.

        Returns:
            True if enabled, False if disabled.
        """
        return self._enabled.get(player_unique_id, True)

    def set_enabled(self, player_unique_id: str, enabled: bool) -> None:
        """Set whether metadata lookup is enabled for a player.

        Args:
            player_unique_id: Player's unique identifier.
            enabled: True to enable, False to disable.
        """
        self._enabled[player_unique_id] = enabled
