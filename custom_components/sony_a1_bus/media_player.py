"""Media player platform for the Sony A1 Bus integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TransportState
from .devices.player import Player

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sony A1 Bus media player from a config entry."""
    _LOGGER.debug("Setting up Sony A1 Bus media player platform")

    # Store the async_add_entities callback for later use
    hass.data[DOMAIN][entry.entry_id]["async_add_media_players"] = async_add_entities

    # Create media players for any already-discovered devices
    # Note: device_registries is a dict of bridge_device_id -> DeviceRegistry
    device_registries = hass.data[DOMAIN][entry.entry_id].get("device_registries", {})
    for device_registry in device_registries.values():
        for player in device_registry.get_all_devices():
            if player.media_player is None:
                async_add_media_player_for_device(hass, entry, player)

    _LOGGER.debug("Sony A1 Bus media player platform setup complete")


class SonyA1BusMediaPlayer(MediaPlayerEntity):
    """Media player entity for a Control-A1 bus device."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name
    _attr_icon = "mdi:disc-player"

    def __init__(self, hass: HomeAssistant, player: Player, entry: ConfigEntry) -> None:
        """Initialize the media player for a given device."""
        self._hass = hass
        self._player = player
        self._entry = entry
        self._attr_unique_id = f"{player.unique_id}_media_player"

        # Set up device info
        device_registry = dr.async_get(hass)
        bridge_device = device_registry.async_get(player.bridge_device_id)
        via_device_id = None
        if bridge_device is not None:
            via_device_id = bridge_device.id

        device_info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, player.unique_id)},
            "name": player.name,
            "manufacturer": "Sony",
            "model": self._get_model_name(),
        }
        if via_device_id is not None:
            device_info_kwargs["via_device_id"] = via_device_id

        self._attr_device_info = DeviceInfo(**device_info_kwargs)

        # Set supported features
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
        )

        # Set callback to update device name in registry when it changes
        def update_device_name(name: str) -> None:
            dev_reg = dr.async_get(self._hass)
            device_entry = dev_reg.async_get_device_by_identifier(
                (DOMAIN, player.unique_id),
                self._entry.entry_id
            )
            if device_entry is not None:
                dev_reg.async_update_device(device_entry.id, name=name, model=name)

        player.set_device_name_update_callback(update_device_name)

    def _get_model_name(self) -> str:
        """Get the model name for this device."""
        if self._player.device_name:
            return self._player.device_name
        if self._player.device_capabilities is not None:
            return f"Device 0x{self._player.device_capabilities:02X}"
        return "Unknown"

    def _track_index(self) -> int | None:
        """Return 0-based track index, or None if invalid."""
        if self._player.current_track > 0:
            return self._player.current_track - 1
        return None

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the media player."""
        if not self._player.power_on:
            return MediaPlayerState.OFF

        state_map = {
            TransportState.PLAYING: MediaPlayerState.PLAYING,
            TransportState.PAUSED: MediaPlayerState.PAUSED,
            TransportState.STOPPED: MediaPlayerState.IDLE,
            TransportState.RECORDING: MediaPlayerState.PLAYING,
            TransportState.RECORD_PAUSE: MediaPlayerState.PAUSED,
        }
        return state_map.get(self._player.transport_state, MediaPlayerState.IDLE)

    @property
    def media_track(self) -> int | None:
        """Return the current track number."""
        if self._player.disc_loaded and self._player.current_track > 0:
            return self._player.current_track
        return None

    @property
    def media_duration(self) -> int | None:
        """Return the duration of the current track in seconds."""
        if self._player.disc_loaded and self._player.current_track > 0:
            return self._player.track_duration_minutes * 60 + self._player.track_duration_seconds
        return None

    @property
    def media_position(self) -> int | None:
        """Return the current position in seconds."""
        if self._player.disc_loaded and self._player.current_track > 0:
            return int(self._player.time_estimator.get_position())
        return None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return the time when the position was last updated."""
        return self._player.time_estimator.last_update_time

    @property
    def media_title(self) -> str | None:
        """Return the title of the current track."""
        idx = self._track_index()
        if idx is None:
            return None
        if self._player.external_metadata and idx < len(self._player.external_metadata.tracks):
            return self._player.external_metadata.tracks[idx].title
        if self._player.disc_loaded and idx < len(self._player.toc):
            return self._player.get_track_title(idx)
        if self._player.current_track > 0:
            return f"Track {self._player.current_track:02d}"
        return None

    @property
    def media_artist(self) -> str | None:
        """Return the artist of the current track."""
        idx = self._track_index()
        if idx is None:
            return None
        if self._player.external_metadata:
            if idx < len(self._player.external_metadata.tracks):
                return self._player.external_metadata.tracks[idx].artist
            return self._player.external_metadata.artist
        if self._player.current_track > 0:
            return "Unknown Artist"
        return None

    @property
    def media_album_name(self) -> str | None:
        """Return the album name."""
        idx = self._track_index()
        if idx is None:
            return None
        if self._player.external_metadata:
            return self._player.external_metadata.album_title
        if self._player.current_track > 0:
            return "Unknown Album"
        return None

    @property
    def media_album_artist(self) -> str | None:
        """Return the album artist."""
        idx = self._track_index()
        if idx is None:
            return None
        if self._player.external_metadata:
            return self._player.external_metadata.artist
        if self._player.current_track > 0:
            return "Unknown Artist"
        return None

    @property
    def media_image_url(self) -> str | None:
        """Return the album art URL."""
        if self._player.external_metadata and self._player.external_metadata.album_art_url:
            return self._player.external_metadata.album_art_url
        return None

    @property
    def entity_picture(self) -> str | None:
        """Return the album art URL."""
        if self._player.external_metadata and self._player.external_metadata.album_art_url:
            return self._player.external_metadata.album_art_url
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {
            "disc_number": self._player.current_disc,
            "disc_loaded": self._player.disc_loaded,
            "track_count": self._player.track_count,
            "shuffle": self._player.shuffle,
            "repeat_all": self._player.repeat_all,
            "repeat_one": self._player.repeat_one,
            "program": self._player.program,
        }
        if self._player.track_count > 0:
            attrs["total_time"] = f"{self._player.total_minutes}:{self._player.total_seconds:02d}"
        if self._player.disc_title is not None:
            attrs["disc_title"] = self._player.disc_title
        if self._player.external_metadata:
            attrs["external_metadata"] = {
                "source": self._player.external_metadata.source,
                "source_id": self._player.external_metadata.source_id,
                "album": self._player.external_metadata.album_title,
                "artist": self._player.external_metadata.artist,
            }
        return attrs

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._player.async_play()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._player.async_pause()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._player.async_stop()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._player.async_next_track()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._player.async_previous_track()


@callback
def async_add_media_player_for_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    player: Player,
) -> None:
    """Create and register a media player entity for a newly discovered device."""
    _LOGGER.debug("Creating media player for device: %s", player.name)
    media_player = SonyA1BusMediaPlayer(hass, player, entry)
    player.media_player = media_player

    async_add_media_players = hass.data[DOMAIN][entry.entry_id].get(
        "async_add_media_players"
    )
    if async_add_media_players is not None:
        _LOGGER.debug("Adding media player to platform")
        async_add_media_players([media_player])
    else:
        _LOGGER.error("async_add_media_players callback not found!")
