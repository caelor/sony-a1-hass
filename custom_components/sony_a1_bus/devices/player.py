"""Base Player class for Control-A1 bus devices.

Represents a single piece of HiFi equipment on the bus. Handles universal
messages (power, transport, status) and provides an interface for device-specific
subclasses to handle their own message types.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from ..const import (
    TOC_MAX_RETRIES,
    TOC_RETRY_TIMEOUT_SEC,
    CommandType,
    DeviceType,
    ResponseType,
    TocState,
    TransportState,
)
from ..external_metadata.models import ExternalMetadata
from ..protocol import (
    Codec,
    DeviceCapacityMessage,
    DeviceNameMessage,
    DiscInfoMessage,
    DiscLoadedMessage,
    Message,
    PowerMessage,
    StatusMessage,
    TimeUpdateMessage,
    TrackChangeMessage,
    TrackEndApproachingMessage,
    TrackInfoMessage,
    TransportMessage,
)
from .time_estimator import TimeEstimator

if TYPE_CHECKING:
    from homeassistant.components.binary_sensor import BinarySensorEntity

    from ..media_player import SonyA1BusMediaPlayer
    from ..sensor import SonyA1BusDeviceSensor

_LOGGER = logging.getLogger(__name__)


class Player:
    """Base class for Control-A1 bus player devices.

    Manages device state and handles universal messages. Subclasses implement
    device-specific message handling.
    """

    def __init__(
        self,
        device_type: DeviceType,
        sub_index: int,
        codec: Codec,
        bridge_node: str,
        bridge_device_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the player.

        Args:
            device_type: Type of device (CD, MD, etc.)
            sub_index: Sub-device index (0-7)
            codec: Device-specific codec for decoding values
            bridge_node: Name of the ESPHome bridge node
            bridge_device_id: HA device ID of the bridge
            hass: Home Assistant instance
        """
        self.hass = hass
        self.device_type = device_type
        self.sub_index = sub_index
        self.codec = codec
        self.bridge_node = bridge_node
        self.bridge_device_id = bridge_device_id

        # Device state
        self.power_on: bool = False
        self.disc_loaded: bool = False
        self.transport_state: TransportState = TransportState.STOPPED
        self.current_disc: int = 1
        self.current_track: int = 0
        self.track_count: int = 0
        self.total_minutes: int = 0
        self.total_seconds: int = 0
        self.track_duration_minutes: int = 0
        self.track_duration_seconds: int = 0
        self.device_name: str | None = None
        self.device_capabilities: int | None = None
        self.disc_count: int = 1
        self.disc_title: str | None = None

        # Table of Contents - list of track dicts with keys:
        # length_min, length_sec, length (total seconds)
        # "title" key is set when a title is read from the bus
        self.toc: list[dict[str, Any]] = []

        # TOC state tracking
        self._toc_state: TocState = TocState.COMPLETE
        self._toc_retry_count: int = 0
        self._toc_retry_timer: asyncio.TimerHandle | None = None
        self._toc_state_listeners: list[Callable[[], None]] = []

        # External metadata from MusicBrainz or other sources
        self.external_metadata: ExternalMetadata | None = None

        # Callback for TOC completion (set by coordinator)
        self._toc_complete_callback: Callable[[], Awaitable[None]] | None = None

        # Playback modes
        self.shuffle: bool = False
        self.program: bool = False
        self.repeat_all: bool = False
        self.repeat_one: bool = False

        # S3 status fields
        self.input_source: str = "Unknown"
        self.mono: bool = False

        # Time estimator for tracking playback position
        self.time_estimator = TimeEstimator()

        # Entity references (set when entities are created)
        self.media_player: SonyA1BusMediaPlayer | None = None
        self.sensors: list[SonyA1BusDeviceSensor] = []
        self.binary_sensors: list[BinarySensorEntity] = []

        # Callback for sending commands (set by device registry)
        self._send_command_callback: Callable[[bytes], Awaitable[bool]] | None = None
        # Callback for updating device name in registry (set by media player)
        self._update_device_name_callback: Callable[[str], None] | None = None

    @property
    def canonical_address(self) -> int:
        """Return the canonical 'to' address for this device."""
        type_code = self.device_type & 0xF0
        return type_code | self.sub_index

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this device."""
        return f"{self.bridge_node}_{self.device_type:02x}_{self.sub_index}"

    @property
    def name(self) -> str:
        """Return a human-readable name for this device."""
        if self.device_name:
            return self.device_name
        type_name = {
            DeviceType.CD_PLAYER: "CD",
            DeviceType.MD_RECORDER: "MD",
            DeviceType.AMPLIFIER: "AMP",
            DeviceType.TUNER: "Tuner",
            DeviceType.SURROUND: "Surround",
        }.get(self.device_type, "Unknown")
        return f"{type_name}-{self.sub_index}"

    @property
    def toc_state(self) -> TocState:
        """Return the current TOC state."""
        return self._toc_state

    def _set_toc_state(self, state: TocState) -> None:
        """Update the TOC state and notify listeners."""
        if self._toc_state == state:
            return
        self._toc_state = state
        for listener in self._toc_state_listeners:
            listener()

    def add_toc_state_listener(self, listener: Callable[[], None]) -> None:
        """Add a listener for TOC state changes."""
        self._toc_state_listeners.append(listener)

    def remove_toc_state_listener(self, listener: Callable[[], None]) -> None:
        """Remove a listener for TOC state changes."""
        if listener in self._toc_state_listeners:
            self._toc_state_listeners.remove(listener)

    def _start_toc_timer(self) -> None:
        """Start the TOC retry timer."""
        self._cancel_toc_timer()
        self._toc_retry_timer = self.hass.loop.call_later(
            TOC_RETRY_TIMEOUT_SEC, self._on_toc_timeout
        )

    def _cancel_toc_timer(self) -> None:
        """Cancel the TOC retry timer if active."""
        if self._toc_retry_timer is not None:
            self._toc_retry_timer.cancel()
            self._toc_retry_timer = None

    def _on_toc_timeout(self) -> None:
        """Handle TOC retry timeout."""
        self._toc_retry_timer = None

        if not self.disc_loaded:
            return

        if self._toc_retry_count >= TOC_MAX_RETRIES:
            _LOGGER.warning(
                "TOC incomplete for %s after %d retries",
                self.name,
                self._toc_retry_count,
            )
            self._set_toc_state(TocState.INCOMPLETE)
            return

        self._toc_retry_count += 1
        _LOGGER.debug(
            "TOC retry %d/%d for %s",
            self._toc_retry_count,
            TOC_MAX_RETRIES,
            self.name,
        )
        encoded_disc = self.codec.encode_byte(self.current_disc)
        asyncio.ensure_future(
            self.async_send_command(
                bytes([CommandType.QUERY_DISC, encoded_disc])
            )
        )
        self._start_toc_timer()

    async def async_refresh_toc(self) -> bool:
        """Manually trigger a TOC re-read.

        Resets retry counter and re-queries the disc.

        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.disc_loaded:
            return False

        self._cancel_toc_timer()
        self._toc_retry_count = 0
        self._set_toc_state(TocState.LOADING)
        self._start_toc_timer()

        encoded_disc = self.codec.encode_byte(self.current_disc)
        return await self.async_send_command(
            bytes([CommandType.QUERY_DISC, encoded_disc])
        )

    def get_track_title(self, track_index: int) -> str:
        """Return the title for a track, with fallback to default.
        
        Args:
            track_index: Zero-based track index
            
        Returns:
            Track title if set, otherwise "Track NN" default
        """
        if track_index < len(self.toc) and "title" in self.toc[track_index]:
            return self.toc[track_index]["title"]
        return f"Track {track_index + 1:02d}"

    def handle_message(self, message: Message) -> list[bytes]:
        """Handle an incoming message from the bus.

        Args:
            message: Decoded message object

        Returns:
            List of command payloads (without address byte) to transmit back to the bus
        """
        responses: list[bytes] = []

        # Handle universal messages
        if isinstance(message, PowerMessage):
            responses = self._handle_power_message(message)
        elif isinstance(message, TransportMessage):
            responses = self._handle_transport_message(message)
        elif isinstance(message, StatusMessage):
            responses = self._handle_status_message(message)
        elif isinstance(message, DiscInfoMessage):
            responses = self._handle_disc_info_message(message)
        elif isinstance(message, TrackInfoMessage):
            responses = self._handle_track_info_message(message)
        elif isinstance(message, TrackChangeMessage):
            responses = self._handle_track_change_message(message)
        elif isinstance(message, TimeUpdateMessage):
            responses = self._handle_time_update_message(message)
        elif isinstance(message, TrackEndApproachingMessage):
            responses = self._handle_track_end_approaching_message(message)
        elif isinstance(message, DeviceCapacityMessage):
            responses = self._handle_device_capacity_message(message)
        elif isinstance(message, DeviceNameMessage):
            responses = self._handle_device_name_message(message)
        elif isinstance(message, DiscLoadedMessage):
            responses = self._handle_disc_loaded_message(message)
        elif message.command == ResponseType.EJECT:
            responses = self._handle_eject_message(message)
        elif message.command == ResponseType.DEVICE_READY:
            responses = self._handle_device_ready_message(message)
        else:
            # Let subclasses handle device-specific messages
            is_handled, responses = self._handle_device_specific_message(message)

            if not is_handled:
                _LOGGER.warning(
                    "Unhandled message for %s: %s",
                    self.name,
                    message,
                )

        if not responses:
            if self.device_capabilities is None:
                responses = [bytes([CommandType.QUERY_CAPACITY])]
            elif self.device_name is None:
                responses = [bytes([CommandType.QUERY_DEVICE_NAME])]

        # Notify entities of state change
        self._notify_entities()

        return responses

    def _handle_power_message(self, message: PowerMessage) -> list[bytes]:
        """Handle power on/off message."""
        self.power_on = message.power_on
        if not message.power_on:
            self.transport_state = TransportState.STOPPED
        return []

    def _handle_transport_message(self, message: TransportMessage) -> list[bytes]:
        """Handle transport state message (play, stop, pause)."""
        self.power_on = True  # Device sending messages must be on

        if message.command == ResponseType.PLAYING:
            self.transport_state = TransportState.PLAYING
            self.time_estimator.play()
        elif message.command == ResponseType.STOPPED:
            self.transport_state = TransportState.STOPPED
            self.time_estimator.stop()
        elif message.command == ResponseType.PAUSED:
            self.transport_state = TransportState.PAUSED
            self.time_estimator.pause()

        return []

    def _handle_status_message(self, message: StatusMessage) -> list[bytes]:
        """Handle 0x70 status message."""
        self.power_on = message.power_on
        responses = self._set_disc_loaded(message.disc_loaded, message.disc_number, True) # status messages can hammer disc loaded state
        self.transport_state = message.transport_state
        self.current_disc = message.disc_number
        self.current_track = message.track_number
        self.shuffle = message.shuffle
        self.program = message.program
        self.repeat_all = message.repeat_all
        self.repeat_one = message.repeat_one
        self.input_source = message.input_source
        self.mono = message.mono

        # Sync time estimator state
        if message.transport_state == TransportState.PLAYING:
            self.time_estimator.play()
        elif message.transport_state == TransportState.PAUSED:
            self.time_estimator.pause()
        elif message.transport_state == TransportState.STOPPED:
            self.time_estimator.stop()

        return responses

    def _handle_disc_info_message(self, message: DiscInfoMessage) -> list[bytes]:
        """Handle 0x60 disc info message."""
        self.current_disc = message.disc_number
        self.track_count = message.track_count
        self.total_minutes = message.total_minutes
        self.total_seconds = message.total_seconds

        self.toc = []
        self.external_metadata = None
        self.disc_title = None
        for i in range(1, message.track_count + 1):
            self.toc.append({
                "length_min": 0,
                "length_sec": 0,
                "length": 0,
            })

        self._set_toc_state(TocState.LOADING)
        self._start_toc_timer()

        return self._progress_toc()

    def _handle_track_info_message(self, message: TrackInfoMessage) -> list[bytes]:
        """Handle 0x62 track info message."""
        if message.track_number < 1 or message.track_number > len(self.toc):
            _LOGGER.warning(
                "Received track info for track %d but TOC has %d tracks for %s",
                message.track_number,
                len(self.toc),
                self.name,
            )
            return []

        track_index = message.track_number - 1
        self.toc[track_index]["length_min"] = message.minutes
        self.toc[track_index]["length_sec"] = message.seconds
        self.toc[track_index]["length"] = message.minutes * 60 + message.seconds

        return self._progress_toc()

    def _progress_toc(self) -> list[bytes]:
        """Query the next track with unknown length.

        Returns:
            List containing 0x45 command to query next track, or empty list if complete.
        """
        for i, track in enumerate(self.toc):
            if track["length"] == 0:
                track_number = i + 1
                encoded_disc = self.codec.encode_byte(self.current_disc)
                encoded_track = self.codec.encode_byte(track_number)
                return [bytes([CommandType.QUERY_TRACK, encoded_disc, encoded_track])]

        responses = self._progress_device_specific_toc()

        if not responses and self.toc:
            _LOGGER.debug("TOC complete for %s", self.name)
            self._cancel_toc_timer()
            self._toc_retry_count = 0
            self._set_toc_state(TocState.COMPLETE)
            self.external_metadata = None
            if self._toc_complete_callback:
                asyncio.ensure_future(self._toc_complete_callback())

        return responses

    def _progress_device_specific_toc(self) -> list[bytes]:
        """Hook for device-specific TOC completion processing.

        Override in subclasses to handle device-specific TOC tasks.
        Called when all tracks have their length populated.
        """
        return []

    def _handle_track_change_message(self, message: TrackChangeMessage) -> list[bytes]:
        """Handle 0x50 track change message (track duration)."""
        self.current_disc = message.disc_number
        self.current_track = message.track_number
        self.track_duration_minutes = message.minutes
        self.track_duration_seconds = message.seconds
        self.time_estimator.set_position(0.0)

        # If we receive a track change but transport state is not playing,
        # query the device status to sync state
        if self.transport_state != TransportState.PLAYING:
            return [bytes([CommandType.QUERY_STATUS]), bytes([CommandType.CMD_SEND_TIME_UPDATES])]

        return [bytes([CommandType.CMD_SEND_TIME_UPDATES])]

    def _handle_time_update_message(self, message: TimeUpdateMessage) -> list[bytes]:
        """Handle 0x51 time update message."""
        self.current_track = message.track_number
        if message.disc_number is not None:
            self.current_disc = message.disc_number
        self.current_minutes = message.minutes
        self.current_seconds = message.seconds
        self.time_estimator.set_position(message.minutes * 60 + message.seconds)
        return []

    def _handle_track_end_approaching_message(self, message: TrackEndApproachingMessage) -> list[bytes]:
        """Handle 0x0C track end approaching message.
        
        Sets the time estimator to 30 seconds before the end of the track.
        Requires track duration to be known (from 0x50 track change message).
        """
        track_duration_seconds = self.track_duration_minutes * 60 + self.track_duration_seconds
        
        if track_duration_seconds == 0:
            _LOGGER.warning(
                "Received track end approaching but track duration unknown for %s",
                self.name,
            )
            return []
        
        position = track_duration_seconds - 30
        self.time_estimator.set_position(position)
        return []

    def _handle_device_capacity_message(self, message: DeviceCapacityMessage) -> list[bytes]:
        """Handle 0x61 device capacity message."""
        self.disc_count = message.disc_count
        self.device_capabilities = message.device_capabilities
        return []

    def _handle_device_name_message(self, message: DeviceNameMessage) -> list[bytes]:
        """Handle 0x6A device name message."""
        self.device_name = message.name
        if self._update_device_name_callback is not None:
            self._update_device_name_callback(message.name)
        return []

    def _set_disc_loaded(self, loaded: bool, disc_number: int = 1, origin_is_status: bool = False) -> list[bytes]:
        """Centralized disc_loaded state management.

        Sets the disc_loaded flag and returns commands to send in response.
        On false->true transition, sends 0x44 Query Disc to fetch disc info.

        Args:
            loaded: Whether a disc is now loaded
            disc_number: Disc number (1-based, for 0x44 query)

        Returns:
            List of command payload to transmit back to the bus
        """
        was_loaded = self.disc_loaded
        self.disc_loaded = loaded

        if not loaded:
            self._cancel_toc_timer()
            self._toc_retry_count = 0
            self._set_toc_state(TocState.COMPLETE)
            self.toc = []
            self.external_metadata = None
            self.disc_title = None

        responses: list[bytes] = []

        if loaded:
            # Disc loaded - query disc info
            # always query on a disc load (not was_loaded), and if the origin was not a status message
            if not was_loaded or not origin_is_status:
                encoded_disc = self.codec.encode_byte(disc_number)
                responses.append(bytes([CommandType.QUERY_DISC, encoded_disc]))

            if was_loaded and not origin_is_status:
                # Unexpected: already thought disc was loaded
                _LOGGER.warning(
                    "Unexpected disc_loaded=true for %s (disc %d) - already in loaded state",
                    self.name,
                    disc_number,
                )

        return responses

    def _handle_eject_message(self, message: Message) -> list[bytes]:
        """Handle 0x03 TOC Updated / Eject message.
        
        Sets disc_loaded to false. No follow-up query needed.
        """
        return self._set_disc_loaded(False)

    def _handle_disc_loaded_message(self, message: DiscLoadedMessage) -> list[bytes]:
        """Handle 0x58 disc loaded message.
        
        Base implementation - subclasses may override for device-specific behavior.
        """
        return self._set_disc_loaded(True, message.disc_number)

    def _handle_device_ready_message(self, message: Message) -> list[bytes]:
        """Handle 0x08 device ready message.
        Assumption: disc_number=01 (no DD field identified in 0x08 params).
        """
        _LOGGER.debug("0x08 message assuming disc_number is 1 for follow-on disc query for %s", self.name)
        return self._set_disc_loaded(True, disc_number=1)

    def _handle_device_specific_message(self, message: Message) -> tuple[bool, list[bytes]]:
        """Handle device-specific messages.

        Override in subclasses to handle device-specific message types.
        """
        return False, []

    def _notify_entities(self) -> None:
        """Notify all entities of state change."""
        if self.media_player is not None:
            self.media_player.async_write_ha_state()
        for sensor in self.sensors:
            sensor.async_write_ha_state()
        for binary_sensor in self.binary_sensors:
            binary_sensor.async_write_ha_state()

    async def async_send_command(self, data: bytes) -> bool:
        """Send a command to this device via the bridge.

        Args:
            data: Raw command bytes (without address byte)

        Returns:
            True if command sent successfully, False otherwise
        """
        if self._send_command_callback is None:
            _LOGGER.warning(
                "Cannot send command to %s: no send callback registered",
                self.name,
            )
            return False

        # Prepend the device's "to" address
        full_data = bytes([self.canonical_address]) + data
        return await self._send_command_callback(full_data)

    async def async_query_status(self) -> bool:
        """Send 0x0F query status command to device.

        Returns:
            True if command sent successfully, False otherwise
        """
        return await self.async_send_command(bytes([CommandType.QUERY_STATUS]))

    async def async_play(self) -> bool:
        """Send play command to device.

        Returns:
            True if command sent successfully, False otherwise
        """
        return await self.async_send_command(bytes([CommandType.CMD_PLAY]))

    async def async_pause(self) -> bool:
        """Send pause command to device.

        Returns:
            True if command sent successfully, False otherwise
        """
        return await self.async_send_command(bytes([CommandType.CMD_PAUSE]))

    async def async_stop(self) -> bool:
        """Send stop command to device.

        Returns:
            True if command sent successfully, False otherwise
        """
        return await self.async_send_command(bytes([CommandType.CMD_STOP]))

    async def async_next_track(self) -> bool:
        """Send next track command to device.

        Returns:
            True if command sent successfully, False otherwise
        """
        return await self.async_send_command(bytes([CommandType.CMD_SKIP_NEXT]))

    async def async_previous_track(self) -> bool:
        """Send previous track command to device.

        Returns:
            True if command sent successfully, False otherwise
        """
        return await self.async_send_command(bytes([CommandType.CMD_SKIP_PREVIOUS]))

    async def async_query_disc(self, disc_number: int = 1) -> bool:
        """Send 0x44 query disc command to device.

        Args:
            disc_number: Disc number to query (1-based, BCD encoded for CD)

        Returns:
            True if command sent successfully, False otherwise
        """
        encoded_disc = self.codec.encode_byte(disc_number)
        return await self.async_send_command(
            bytes([CommandType.QUERY_DISC, encoded_disc])
        )



    def set_send_callback(self, callback: Callable[[bytes], Awaitable[bool]]) -> None:
        """Set the callback for sending commands to the bus.

        Args:
            callback: Async function that takes raw bytes and sends them to the bus,
                     returning True on success, False on failure
        """
        self._send_command_callback = callback

    def set_device_name_update_callback(self, callback: Callable[[str], None]) -> None:
        """Set the callback for updating device name in the registry.

        Args:
            callback: Function that takes a string name and updates the device registry
        """
        self._update_device_name_callback = callback

    def set_toc_complete_callback(self, callback: Callable[[], Awaitable[None]] | None) -> None:
        """Set the callback for TOC completion.

        Args:
            callback: Async function called when TOC is fully populated, or None to clear.
        """
        self._toc_complete_callback = callback
