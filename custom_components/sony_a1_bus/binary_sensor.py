"""Binary sensor platform for the Sony A1 Bus integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices.player import Player

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sony A1 Bus binary sensor from a config entry."""
    _LOGGER.debug("Setting up Sony A1 Bus binary sensor platform")

    hass.data[DOMAIN][entry.entry_id]["async_add_binary_sensors"] = async_add_entities

    device_registries = hass.data[DOMAIN][entry.entry_id].get("device_registries", {})
    for device_registry in device_registries.values():
        for player in device_registry.get_all_devices():
            if not player.binary_sensors:
                async_add_binary_sensors_for_device(hass, entry, player)

    _LOGGER.debug("Sony A1 Bus binary sensor platform setup complete")


class SonyA1BusBinarySensor(BinarySensorEntity):
    """Base binary sensor entity for a Control-A1 bus device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
        sensor_name: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the binary sensor."""
        self._player = player
        self._entry = entry
        self._attr_name = sensor_name
        self._attr_unique_id = f"{player.unique_id}_{unique_id_suffix}"

        device_info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, player.unique_id)},
        }
        self._attr_device_info = DeviceInfo(**device_info_kwargs)


class SonyA1BusMonoSensor(SonyA1BusBinarySensor):
    """Binary sensor showing whether mono mode is active."""

    _attr_icon = "mdi:volume-high"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the mono sensor."""
        super().__init__(hass, player, entry, "Mono", "mono")

    @property
    def is_on(self) -> bool:
        """Return true if mono mode is active."""
        return self._player.mono


class SonyA1BusPowerSensor(SonyA1BusBinarySensor):
    """Binary sensor showing whether the device is powered on."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(hass, player, entry, "Power", "power")

    @property
    def is_on(self) -> bool:
        """Return true if the device is powered on."""
        return self._player.power_on


class SonyA1BusDiscLoadedSensor(SonyA1BusBinarySensor):
    """Binary sensor showing whether a disc is loaded."""

    _attr_icon = "mdi:disc"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the disc loaded sensor."""
        super().__init__(hass, player, entry, "Disc Loaded", "disc_loaded")

    @property
    def is_on(self) -> bool:
        """Return true if a disc is loaded."""
        return self._player.disc_loaded

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {"toc": self._player.toc}


class SonyA1BusShuffleSensor(SonyA1BusBinarySensor):
    """Binary sensor showing whether shuffle mode is active."""

    _attr_icon = "mdi:shuffle-variant"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the shuffle sensor."""
        super().__init__(hass, player, entry, "Shuffle", "shuffle")

    @property
    def is_on(self) -> bool:
        """Return true if shuffle mode is active."""
        return self._player.shuffle


class SonyA1BusProgramSensor(SonyA1BusBinarySensor):
    """Binary sensor showing whether program mode is active."""

    _attr_icon = "mdi:playlist-music"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the program sensor."""
        super().__init__(hass, player, entry, "Program", "program")

    @property
    def is_on(self) -> bool:
        """Return true if program mode is active."""
        return self._player.program


class SonyA1BusRepeatAllSensor(SonyA1BusBinarySensor):
    """Binary sensor showing whether repeat-all mode is active."""

    _attr_icon = "mdi:repeat"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the repeat all sensor."""
        super().__init__(hass, player, entry, "Repeat All", "repeat_all")

    @property
    def is_on(self) -> bool:
        """Return true if repeat-all mode is active."""
        return self._player.repeat_all


class SonyA1BusRepeatOneSensor(SonyA1BusBinarySensor):
    """Binary sensor showing whether repeat-one mode is active."""

    _attr_icon = "mdi:repeat-once"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the repeat one sensor."""
        super().__init__(hass, player, entry, "Repeat One", "repeat_one")

    @property
    def is_on(self) -> bool:
        """Return true if repeat-one mode is active."""
        return self._player.repeat_one


@callback
def async_add_binary_sensors_for_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    player: Player,
) -> None:
    """Create and register binary sensor entities for a device."""
    _LOGGER.debug("Creating binary sensors for device: %s", player.name)

    sensors: list[BinarySensorEntity] = [
        SonyA1BusMonoSensor(hass, player, entry),
        SonyA1BusPowerSensor(hass, player, entry),
        SonyA1BusDiscLoadedSensor(hass, player, entry),
        SonyA1BusShuffleSensor(hass, player, entry),
        SonyA1BusProgramSensor(hass, player, entry),
        SonyA1BusRepeatAllSensor(hass, player, entry),
        SonyA1BusRepeatOneSensor(hass, player, entry),
    ]

    player.binary_sensors.extend(sensors)

    async_add_binary_sensors = hass.data[DOMAIN][entry.entry_id].get("async_add_binary_sensors")
    if async_add_binary_sensors is not None:
        _LOGGER.debug("Adding binary sensors to platform")
        async_add_binary_sensors(sensors)
    else:
        _LOGGER.error("async_add_binary_sensors callback not found!")
