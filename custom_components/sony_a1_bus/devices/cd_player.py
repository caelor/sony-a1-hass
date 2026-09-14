"""CD Player device implementation."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from ..const import DeviceType, ResponseType
from ..protocol import BCDCodec, DiscLoadedMessage, Message
from .player import Player

_LOGGER = logging.getLogger(__name__)


class CDPlayer(Player):
    """CD Player device on the Control-A1 bus.

    Uses BCD encoding for numeric values. Handles CD-specific messages
    like CD Text (0x48-0x4B) in future implementations.
    """

    IGNORED_COMMANDS = [
        0x14,    # Invalid disc - sent during load because the status message indicates disc load before it's read.
        0x52     # Front panel disc display
    ]

    def __init__(
        self,
        sub_index: int,
        bridge_node: str,
        bridge_device_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the CD player.

        Args:
            sub_index: Sub-device index (0-7)
            bridge_node: Name of the ESPHome bridge node
            bridge_device_id: HA device ID of the bridge
            hass: Home Assistant instance
        """
        super().__init__(
            device_type=DeviceType.CD_PLAYER,
            sub_index=sub_index,
            codec=BCDCodec(),
            bridge_node=bridge_node,
            bridge_device_id=bridge_device_id,
            hass=hass,
        )

    def _handle_device_specific_message(self, message: Message) -> tuple[bool, list[bytes]]:
        """Handle CD-specific messages.

        Handles:
        - 0x47: CD-TEXT disc detected (sets disc_loaded=true)
        - 0x58: Disc loaded (CD type - single DD param)
        
        Future implementation will handle:
        - 0x48/0x49: Enhanced disc memo / CD Text
        - 0x4A/0x4B: CD Text track names
        - 0x71: Disc memory information
        """
        if message.command in self.IGNORED_COMMANDS:
            _LOGGER.debug("Ignoring command 0x%02X for %s", message.command, self.name)
            return True, []
        elif message.command == ResponseType.CD_TEXT_DETECTED:
            return True, self._handle_cd_text_detected(message)
        elif message.command == ResponseType.DISC_LOADED:
            return True, self._handle_disc_loaded_cd(message)
        
        return False, []

    def _handle_cd_text_detected(self, message: Message) -> list[bytes]:
        """Handle 0x47 CD-TEXT disc detected.
        
        Parameters are unknown/ignored. Just marks disc as loaded.
        Assumption: disc_number=01 (no DD field identified in 0x47 params).
        """
        _LOGGER.debug("CD-TEXT disc detected for %s", self.name)
        return self._set_disc_loaded(True, disc_number=1)

    def _handle_disc_loaded_cd(self, message: DiscLoadedMessage) -> list[bytes]:
        """Handle 0x58 Loaded disc (CD type - single DD param)."""
        return self._set_disc_loaded(True, message.disc_number)
