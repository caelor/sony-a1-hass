"""MiniDisc Player device implementation."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from ..const import CommandType, DeviceType, ResponseType, TransportState
from ..protocol import (
    DiscLoadedMessage,
    DiscTextContinuationMessage,
    DiscTextFirstBlockMessage,
    HexCodec,
    Message,
    TrackTextContinuationMessage,
    TrackTextFirstBlockMessage,
)
from .player import Player
from .title_reassembler import TitleReassembler

_LOGGER = logging.getLogger(__name__)


class MDPlayer(Player):
    """MiniDisc Player device on the Control-A1 bus.

    Uses raw hex encoding for numeric values. Handles MD-specific messages
    like record states and disc/track text (0x58-0x5B).
    """

    def __init__(
        self,
        sub_index: int,
        bridge_node: str,
        bridge_device_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the MD player.

        Args:
            sub_index: Sub-device index (0-7)
            bridge_node: Name of the ESPHome bridge node
            bridge_device_id: HA device ID of the bridge
            hass: Home Assistant instance
        """
        super().__init__(
            device_type=DeviceType.MD_RECORDER,
            sub_index=sub_index,
            codec=HexCodec(),
            bridge_node=bridge_node,
            bridge_device_id=bridge_device_id,
            hass=hass,
        )
        self._title_reassembler: TitleReassembler | None = None
        self._title_reassembler_track: int | None = None

    def _handle_device_specific_message(self, message: Message) -> tuple[bool, list[bytes]]:
        """Handle MD-specific messages.

        Handles:
        - 0x04: Record play
        - 0x07: Record pause
        - 0x58: Disc text first block
        - 0x59: Disc text continuation
        - 0x5A: Track text first block
        - 0x5B: Track text continuation
        - 0x16: No disc name
        - 0x17: No track name
        """
        if message.command == ResponseType.RECORD_PLAY:
            self.transport_state = TransportState.RECORDING
            return True, []
        elif message.command == ResponseType.RECORD_PAUSE_STATE:
            self.transport_state = TransportState.RECORD_PAUSE
            return True, []
        elif isinstance(message, DiscTextFirstBlockMessage):
            return True, self._handle_disc_text_first(message)
        elif isinstance(message, DiscTextContinuationMessage):
            return True, self._handle_disc_text_continuation(message)
        elif isinstance(message, TrackTextFirstBlockMessage):
            return True, self._handle_track_text_first(message)
        elif isinstance(message, TrackTextContinuationMessage):
            return True, self._handle_track_text_continuation(message)
        elif message.command == ResponseType.NO_DISC_NAME:
            return True, self._handle_no_disc_name()
        elif message.command == ResponseType.NO_TRACK_NAME:
            return True, self._handle_no_track_name()

        return False, []

    def _handle_disc_text_first(self, message: DiscTextFirstBlockMessage) -> list[bytes]:
        """Handle 0x58 disc text first block."""
        self._title_reassembler = TitleReassembler(message.title_fragment)
        self._title_reassembler_track = None
        return self._check_title_complete()

    def _handle_disc_text_continuation(self, message: DiscTextContinuationMessage) -> list[bytes]:
        """Handle 0x59 disc text continuation block."""
        if self._title_reassembler is None or self._title_reassembler_track is not None:
            _LOGGER.warning(
                "Received disc text continuation without active disc title reassembly for %s",
                self.name,
            )
            return []
        self._title_reassembler.add_block(message.block_number, message.data)
        return self._check_title_complete()

    def _handle_track_text_first(self, message: TrackTextFirstBlockMessage) -> list[bytes]:
        """Handle 0x5A track text first block."""
        self._title_reassembler = TitleReassembler(message.title_fragment)
        self._title_reassembler_track = message.track_number
        return self._check_title_complete()

    def _handle_track_text_continuation(self, message: TrackTextContinuationMessage) -> list[bytes]:
        """Handle 0x5B track text continuation block."""
        if self._title_reassembler is None or self._title_reassembler_track is None:
            _LOGGER.warning(
                "Received track text continuation without active track title reassembly for %s",
                self.name,
            )
            return []
        self._title_reassembler.add_block(message.block_number, message.data)
        return self._check_title_complete()

    def _check_title_complete(self) -> list[bytes]:
        """Check if current title reassembly is complete and update TOC."""
        if self._title_reassembler is None:
            return []
        title = self._title_reassembler.get_title()
        if title is None:
            return []
        if self._title_reassembler_track is None:
            self.disc_title = title
        else:
            track_index = self._title_reassembler_track - 1
            if 0 <= track_index < len(self.toc):
                self.toc[track_index]["title"] = title
        self._title_reassembler = None
        self._title_reassembler_track = None
        return self._progress_toc()

    def _handle_no_disc_name(self) -> list[bytes]:
        """Handle 0x16 no disc name response."""
        self.disc_title = "No Name"
        return self._progress_toc()

    def _handle_no_track_name(self) -> list[bytes]:
        """Handle 0x17 no track name response."""
        track_number = self._find_current_subject_track()
        if track_number is not None:
            track_index = track_number - 1
            if 0 <= track_index < len(self.toc):
                self.toc[track_index]["title"] = "No Name"
        return self._progress_toc()

    def _find_current_subject_track(self) -> int | None:
        """Find the track number currently being queried for title.
        
        Returns 1-based track number, or None if no track is being queried.
        """
        if self._title_reassembler_track is not None:
            return self._title_reassembler_track
        for i, track in enumerate(self.toc):
            if "title" not in track:
                return i + 1
        return None

    def _find_next_track_without_title(self) -> int | None:
        """Find the first track without a title.
        
        Returns 1-based track number, or None if all tracks have titles.
        """
        for i, track in enumerate(self.toc):
            if "title" not in track:
                return i + 1
        return None

    def _progress_device_specific_toc(self) -> list[bytes]:
        """Progress MD-specific TOC reading (disc and track titles)."""
        if self.disc_title is None:
            encoded_disc = self.codec.encode_byte(self.current_disc)
            return [bytes([CommandType.QUERY_DISC_NAME, encoded_disc, 0x00])]

        track_number = self._find_next_track_without_title()
        if track_number is not None:
            encoded_track = self.codec.encode_byte(track_number)
            return [bytes([CommandType.QUERY_TRACK_NAME, encoded_track, 0x00])]

        return []

    def _handle_disc_loaded_message(self, message: DiscLoadedMessage) -> list[bytes]:
        """Override base class - MD 0x58 is disc text, not disc loaded."""
        return []
