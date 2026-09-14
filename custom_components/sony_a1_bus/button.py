"""Button platform for the Sony A1 Bus integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Set up Sony A1 Bus button from a config entry."""
    _LOGGER.debug("Setting up Sony A1 Bus button platform")

    # Store the async_add_entities callback for later use
    hass.data[DOMAIN][entry.entry_id]["async_add_buttons"] = async_add_entities

    # Create buttons for any already-discovered devices
    device_registries = hass.data[DOMAIN][entry.entry_id].get("device_registries", {})
    for device_registry in device_registries.values():
        for player in device_registry.get_all_devices():
            if not hasattr(player, "_buttons") or not player._buttons:
                async_add_button_for_device(hass, entry, player)

    _LOGGER.debug("Sony A1 Bus button platform setup complete")


class SonyA1BusButton(ButtonEntity):
    """Base button entity for a Control-A1 bus device."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        player: Player,
        entry: ConfigEntry,
        button_name: str,
        unique_id_suffix: str,
        icon: str,
    ) -> None:
        """Initialize the button."""
        self._player = player
        self._entry = entry
        self._attr_name = button_name
        self._attr_icon = icon
        self._attr_unique_id = f"{player.unique_id}_{unique_id_suffix}"

        device_info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, player.unique_id)},
        }
        self._attr_device_info = DeviceInfo(**device_info_kwargs)


class SonyA1BusQueryStatusButton(SonyA1BusButton):
    """Button to query device status."""

    def __init__(self, player: Player, entry: ConfigEntry) -> None:
        """Initialize the query status button."""
        super().__init__(player, entry, "Query Status", "query_status", "mdi:refresh")

    async def async_press(self) -> None:
        """Handle the button press."""
        success = await self._player.async_query_status()
        if not success:
            _LOGGER.warning("Query status command failed for %s", self._player.name)


class SonyA1BusRefreshTocButton(SonyA1BusButton):
    """Button to manually trigger a TOC re-read."""

    def __init__(self, player: Player, entry: ConfigEntry) -> None:
        """Initialize the refresh TOC button."""
        super().__init__(player, entry, "Refresh TOC", "refresh_toc", "mdi:disc-sync")

    async def async_press(self) -> None:
        """Handle the button press."""
        success = await self._player.async_refresh_toc()
        if not success:
            _LOGGER.debug("Refresh TOC skipped for %s (no disc loaded)", self._player.name)


@callback
def async_add_button_for_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    player: Player,
) -> None:
    """Create and register button entities for a device."""
    _LOGGER.debug("Creating buttons for device: %s", player.name)
    buttons: list[ButtonEntity] = [
        SonyA1BusQueryStatusButton(player, entry),
        SonyA1BusRefreshTocButton(player, entry),
    ]
    player._buttons = buttons

    async_add_buttons = hass.data[DOMAIN][entry.entry_id].get("async_add_buttons")
    if async_add_buttons is not None:
        _LOGGER.debug("Adding buttons to platform")
        async_add_buttons(buttons)
    else:
        _LOGGER.error("async_add_buttons callback not found!")
