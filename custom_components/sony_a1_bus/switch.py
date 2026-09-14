"""Switch platform for the Sony A1 Bus integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MetadataCoordinator
from .devices.player import Player

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sony A1 Bus switch from a config entry."""
    _LOGGER.debug("Setting up Sony A1 Bus switch platform")

    hass.data[DOMAIN][entry.entry_id]["async_add_switches"] = async_add_entities

    device_registries = hass.data[DOMAIN][entry.entry_id].get("device_registries", {})
    coordinator: MetadataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    for device_registry in device_registries.values():
        for player in device_registry.get_all_devices():
            if not hasattr(player, "_metadata_switch") or player._metadata_switch is None:
                async_add_switch_for_device(hass, entry, player, coordinator)

    _LOGGER.debug("Sony A1 Bus switch platform setup complete")


class SonyA1BusMetadataSwitch(SwitchEntity):
    """Switch to enable/disable external metadata lookup for a player."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:cloud-search"

    def __init__(
        self,
        hass: HomeAssistant,
        player: Player,
        entry: ConfigEntry,
        coordinator: MetadataCoordinator,
    ) -> None:
        """Initialize the switch."""
        self._hass = hass
        self._player = player
        self._entry = entry
        self._coordinator = coordinator
        self._attr_unique_id = f"{player.unique_id}_metadata_lookup"

        device_info: dict[str, Any] = {
            "identifiers": {(DOMAIN, player.unique_id)},
            "name": player.name,
            "manufacturer": "Sony",
        }
        self._attr_device_info = DeviceInfo(**device_info)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return "External metadata lookup"

    @property
    def is_on(self) -> bool:
        """Return True if metadata lookup is enabled."""
        return self._coordinator.is_enabled(self._player)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable metadata lookup."""
        self._coordinator.set_enabled(self._player, True)
        await self._coordinator.cache.async_save()

        if self._player.toc and all(t["length"] > 0 for t in self._player.toc):
            await self._coordinator.async_on_toc_complete(self._player)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable metadata lookup."""
        self._coordinator.set_enabled(self._player, False)
        await self._coordinator.cache.async_save()

        self._player.external_metadata = None
        self._player._notify_entities()


def async_add_switch_for_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    player: Player,
    coordinator: MetadataCoordinator,
) -> None:
    """Create and register a metadata switch for a player device."""
    _LOGGER.debug("Creating metadata switch for device: %s", player.name)
    switch = SonyA1BusMetadataSwitch(hass, player, entry, coordinator)
    player._metadata_switch = switch

    async_add_switches = hass.data[DOMAIN][entry.entry_id].get("async_add_switches")
    if async_add_switches is not None:
        _LOGGER.debug("Adding metadata switch to platform")
        async_add_switches([switch])
    else:
        _LOGGER.error("async_add_switches callback not found!")
