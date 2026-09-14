"""Device registry and factory for Control-A1 bus devices."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from homeassistant.core import HomeAssistant

from ..const import DeviceType
from ..protocol import AddressInfo
from .cd_player import CDPlayer
from .md_player import MDPlayer
from .player import Player

_LOGGER = logging.getLogger(__name__)


class DeviceRegistry:
    """Registry of active bus devices per bridge.

    Manages the lifecycle of Player instances, creating them opportunistically
    when messages are received from unknown devices.
    """

    def __init__(self, hass: HomeAssistant, bridge_node: str, bridge_device_id: str) -> None:
        """Initialize the device registry.

        Args:
            hass: Home Assistant instance
            bridge_node: Name of the ESPHome bridge node
            bridge_device_id: HA device ID of the bridge
        """
        self.hass = hass
        self.bridge_node = bridge_node
        self.bridge_device_id = bridge_device_id
        self._devices: dict[tuple[DeviceType, int], Player] = {}
        self._send_callback: Callable[[bytes], Awaitable[bool]] | None = None

    def set_send_callback(self, callback: Callable[[bytes], Awaitable[bool]]) -> None:
        """Set the callback for sending commands to the bus.

        Args:
            callback: Async function that takes raw bytes and sends them to the bus,
                     returning True on success, False on failure
        """
        self._send_callback = callback
        # Update existing devices
        for device in self._devices.values():
            device.set_send_callback(callback)

    def get_or_create_device(self, address_info: AddressInfo) -> Player | None:
        """Get an existing device or create a new one.

        Args:
            address_info: Decoded address information from the message

        Returns:
            Player instance, or None if device type is not supported
        """
        # Only create devices for messages FROM the device
        if not address_info.direction_from_device:
            return None

        device_type = address_info.device_type
        sub_index = address_info.sub_index
        key = (device_type, sub_index)

        if key not in self._devices:
            # Create new device
            player = self._create_device(device_type, sub_index)
            if player is None:
                return None

            self._devices[key] = player
            _LOGGER.info(
                "Discovered new bus device: %s (type=%s, sub=%d)",
                player.name,
                device_type.name,
                sub_index,
            )

            # Set send callback if available
            if self._send_callback is not None:
                player.set_send_callback(self._send_callback)

        return self._devices[key]

    def _create_device(
        self, device_type: DeviceType, sub_index: int
    ) -> Player | None:
        """Create a new Player instance for the given device type.

        Args:
            device_type: Type of device to create
            sub_index: Sub-device index

        Returns:
            Player instance, or None if device type is not supported
        """
        if device_type == DeviceType.CD_PLAYER:
            return CDPlayer(
                sub_index=sub_index,
                bridge_node=self.bridge_node,
                bridge_device_id=self.bridge_device_id,
                hass=self.hass,
            )
        elif device_type == DeviceType.MD_RECORDER:
            return MDPlayer(
                sub_index=sub_index,
                bridge_node=self.bridge_node,
                bridge_device_id=self.bridge_device_id,
                hass=self.hass,
            )
        else:
            _LOGGER.warning(
                "Unsupported device type: %s (sub=%d)",
                device_type.name,
                sub_index,
            )
            return None

    def get_device(self, device_type: DeviceType, sub_index: int) -> Player | None:
        """Get an existing device by type and sub-index.

        Args:
            device_type: Type of device
            sub_index: Sub-device index

        Returns:
            Player instance, or None if not found
        """
        return self._devices.get((device_type, sub_index))

    def get_all_devices(self) -> list[Player]:
        """Get all registered devices.

        Returns:
            List of all Player instances
        """
        return list(self._devices.values())
