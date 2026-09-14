"""Sensor platform for the Sony A1 Bus integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BridgeData
from .devices.player import Player

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sony A1 Bus sensor from a config entry."""
    _LOGGER.debug("Setting up Sony A1 Bus sensor platform")
    
    # Store the async_add_entities callback for later use
    hass.data[DOMAIN][entry.entry_id]["async_add_entities"] = async_add_entities
    
    # Create sensors for any already-discovered bridges
    bridges = hass.data[DOMAIN][entry.entry_id]["bridges"]
    for bridge in bridges.values():
        if bridge.get("sensor") is None:
            async_add_sensor_for_bridge(hass, entry, bridge)
    
    _LOGGER.debug("Sony A1 Bus sensor platform setup complete")


class SonyA1BusLastMessageSensor(SensorEntity):
    """Diagnostic sensor showing the most recent Sony A1 Bus message."""

    _attr_has_entity_name = True
    _attr_name = "Last Bus Message"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:bus"

    def __init__(self, hass: HomeAssistant, bridge: BridgeData, entry: ConfigEntry) -> None:
        """Initialize the sensor for a given bridge."""
        self._bridge = bridge
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{bridge['device_id']}_last_message"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bridge["node"])},
        )

    @property
    def native_value(self) -> str | None:
        """Return the hex string of the most recent bus message."""
        return self._bridge.get("last_message") or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {"node": self._bridge["node"]}
        if self._bridge.get("truncated"):
            attrs["truncated"] = True
        return attrs


@callback
def async_add_sensor_for_bridge(
    hass: HomeAssistant,
    entry: ConfigEntry,
    bridge: BridgeData,
) -> None:
    """Create and register a sensor entity for a newly discovered bridge."""
    _LOGGER.debug("Creating sensor for bridge: %s", bridge["node"])
    sensor = SonyA1BusLastMessageSensor(hass, bridge, entry)
    bridge["sensor"] = sensor
    
    async_add_entities = hass.data[DOMAIN][entry.entry_id].get("async_add_entities")
    if async_add_entities is not None:
        _LOGGER.debug("Adding sensor to platform")
        async_add_entities([sensor])
    else:
        _LOGGER.error("async_add_entities callback not found!")


class SonyA1BusDeviceSensor(SensorEntity):
    """Base sensor entity for a Control-A1 bus device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
        sensor_name: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the sensor for a given device."""
        self._player = player
        self._entry = entry
        self._attr_name = sensor_name
        self._attr_unique_id = f"{player.unique_id}_{unique_id_suffix}"

        # Set up device info - link to the device's HA device
        device_info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, player.unique_id)},
        }
        self._attr_device_info = DeviceInfo(**device_info_kwargs)


class SonyA1BusTrackCountSensor(SonyA1BusDeviceSensor):
    """Sensor showing the number of tracks on the current disc."""

    _attr_icon = "mdi:numeric"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the track count sensor."""
        super().__init__(hass, player, entry, "Track Count", "track_count")

    @property
    def native_value(self) -> int | None:
        """Return the number of tracks."""
        if self._player.disc_loaded and self._player.track_count > 0:
            return self._player.track_count
        return None


class SonyA1BusDiscTimeSensor(SonyA1BusDeviceSensor):
    """Sensor showing the total playing time of the current disc."""

    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the disc time sensor."""
        super().__init__(hass, player, entry, "Disc Time", "disc_time")

    @property
    def native_value(self) -> str | None:
        """Return the total disc time as MM:SS."""
        if self._player.disc_loaded and self._player.track_count > 0:
            return f"{self._player.total_minutes}:{self._player.total_seconds:02d}"
        return None


class SonyA1BusInputSourceSensor(SonyA1BusDeviceSensor):
    """Sensor showing the current input source."""

    _attr_icon = "mdi:audio-input-rca"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the input source sensor."""
        super().__init__(hass, player, entry, "Input Source", "input_source")

    @property
    def native_value(self) -> str | None:
        """Return the current input source."""
        return self._player.input_source


class SonyA1BusCurrentDiscSensor(SonyA1BusDeviceSensor):
    """Sensor showing the current disc number."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:disc"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the current disc sensor."""
        super().__init__(hass, player, entry, "Current Disc", "current_disc")

    @property
    def native_value(self) -> int | None:
        """Return the current disc number."""
        if self._player.disc_loaded:
            return self._player.current_disc
        return None


class SonyA1BusCurrentTrackSensor(SonyA1BusDeviceSensor):
    """Sensor showing the current track number."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:numeric"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the current track sensor."""
        super().__init__(hass, player, entry, "Current Track", "current_track")

    @property
    def native_value(self) -> int | None:
        """Return the current track number."""
        if self._player.disc_loaded and self._player.current_track > 0:
            return self._player.current_track
        return None


class SonyA1BusCurrentTrackTimeSensor(SonyA1BusDeviceSensor):
    """Sensor showing the duration of the current track."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the current track time sensor."""
        super().__init__(hass, player, entry, "Current Track Time", "current_track_time")

    @property
    def native_value(self) -> str | None:
        """Return the current track duration as MM:SS."""
        if self._player.disc_loaded and self._player.current_track > 0:
            total_seconds = self._player.track_duration_minutes * 60 + self._player.track_duration_seconds
            if total_seconds > 0:
                return f"{self._player.track_duration_minutes}:{self._player.track_duration_seconds:02d}"
        return None


class SonyA1BusDeviceCapabilitiesSensor(SonyA1BusDeviceSensor):
    """Sensor showing the device capabilities bitmask."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cog"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the device capabilities sensor."""
        super().__init__(hass, player, entry, "Device Capabilities", "device_capabilities")

    @property
    def native_value(self) -> int | None:
        """Return the device capabilities bitmask."""
        return self._player.device_capabilities


class SonyA1BusDiscCountSensor(SonyA1BusDeviceSensor):
    """Sensor showing the number of discs the changer holds."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:disc"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the disc count sensor."""
        super().__init__(hass, player, entry, "Disc Count", "disc_count")

    @property
    def native_value(self) -> int:
        """Return the disc count."""
        return self._player.disc_count


class SonyA1BusTocStateSensor(SonyA1BusDeviceSensor):
    """Sensor showing the current TOC reading state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:table-of-contents"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the TOC state sensor."""
        super().__init__(hass, player, entry, "TOC State", "toc_state")
        self._player.add_toc_state_listener(self._on_toc_state_changed)

    @property
    def native_value(self) -> str:
        """Return the current TOC state."""
        return self._player.toc_state.value

    def _on_toc_state_changed(self) -> None:
        """Handle TOC state change."""
        self.async_write_ha_state()


@callback
def async_add_sensors_for_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    player: Player,
) -> None:
    """Create and register sensor entities for a newly discovered device."""
    _LOGGER.debug("Creating sensors for device: %s", player.name)

    sensors: list[SonyA1BusDeviceSensor] = [
        SonyA1BusTrackCountSensor(hass, player, entry),
        SonyA1BusDiscTimeSensor(hass, player, entry),
        SonyA1BusInputSourceSensor(hass, player, entry),
        SonyA1BusCurrentDiscSensor(hass, player, entry),
        SonyA1BusCurrentTrackSensor(hass, player, entry),
        SonyA1BusCurrentTrackTimeSensor(hass, player, entry),
        SonyA1BusDeviceCapabilitiesSensor(hass, player, entry),
        SonyA1BusDiscCountSensor(hass, player, entry),
        SonyA1BusTocStateSensor(hass, player, entry),
    ]

    # Register sensors with the player
    player.sensors.extend(sensors)

    async_add_entities = hass.data[DOMAIN][entry.entry_id].get("async_add_entities")
    if async_add_entities is not None:
        _LOGGER.debug("Adding sensors to platform")
        async_add_entities(sensors)
    else:
        _LOGGER.error("async_add_entities callback not found!")
