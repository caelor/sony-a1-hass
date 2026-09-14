"""Typed message dataclasses for decoded bus messages.

Each message type represents a specific command or response from the Control-A1
protocol. Messages are created by the protocol decoder and passed to Player
instances for handling.
"""

from dataclasses import dataclass

from ..const import TransportState


@dataclass
class Message:
    """Base class for all bus messages."""

    command: int
    raw_data: bytes

    def __repr__(self) -> str:
            """Returns a string representation with raw_data formatted as a clean hex dump."""
            hex_dump = self.raw_data.hex(' ').upper()
            return f"Message(command={self.command}, raw_data=0x[{hex_dump}])"

@dataclass
class TransportMessage(Message):
    """Transport state change message (play, stop, pause, etc.)."""



@dataclass
class PowerMessage(Message):
    """Power state change message (power on/off)."""

    power_on: bool


@dataclass
class StatusMessage(Message):
    """Status message from 0x70 response.

    Contains transport state, playback modes, and current disc/track.
    """

    transport_state: TransportState
    power_on: bool
    disc_loaded: bool
    shuffle: bool
    program: bool
    repeat_all: bool
    repeat_one: bool
    disc_number: int
    track_number: int
    input_source: str
    mono: bool


@dataclass
class DiscInfoMessage(Message):
    """Disc information from 0x60 response.

    Contains track count and total disc length.
    """

    disc_number: int
    indexes: int
    track_count: int
    total_minutes: int
    total_seconds: int
    frames: int


@dataclass
class TrackInfoMessage(Message):
    """Track information from 0x62 response.

    Contains track length.
    """

    disc_number: int
    track_number: int
    minutes: int
    seconds: int


@dataclass
class TrackChangeMessage(Message):
    """Track change message from 0x50 response.

    Contains track duration (length), not position.
    """

    disc_number: int
    track_number: int
    minutes: int
    seconds: int


@dataclass
class TimeUpdateMessage(Message):
    """Time update from 0x51 response.

    Contains current playback position (sent during time update mode).
    """

    track_number: int
    disc_number: int | None  # MD includes disc, CD does not
    minutes: int
    seconds: int


@dataclass
class DeviceCapacityMessage(Message):
    """Device capacity from 0x61 response.

    Contains disc count and device capabilities bitmask.
    """

    disc_count: int
    device_capabilities: int | None = None


@dataclass
class DeviceNameMessage(Message):
    """Device name from 0x6A response."""

    name: str


@dataclass
class TrackEndApproachingMessage(Message):
    """Track end approaching message from 0x0C response.
    
    Sent 30 seconds before the end of the playing track.
    No parameters - just a notification.
    """


@dataclass
class DiscLoadedMessage(Message):
    """Disc loaded message from 0x58 response (CD only).
    
    Single DD parameter (disc number, BCD encoded).
    """

    disc_number: int


@dataclass
class DiscTextFirstBlockMessage(Message):
    """Disc text first block from 0x58 response (MD only).
    
    Parameters: DD (disc number) 0x00 0x00 CCx14 (14 bytes of title data).
    """

    disc_number: int
    title_fragment: bytes


@dataclass
class DiscTextContinuationMessage(Message):
    """Disc text continuation block from 0x59 response (MD only).
    
    Parameters: BB (block number, >=2) CCx16 (16 bytes of title data).
    """

    block_number: int
    data: bytes


@dataclass
class TrackTextFirstBlockMessage(Message):
    """Track text first block from 0x5A response (MD only).
    
    Parameters: TT (track number) 0x00 0x00 CCx14 (14 bytes of title data).
    """

    track_number: int
    title_fragment: bytes


@dataclass
class TrackTextContinuationMessage(Message):
    """Track text continuation block from 0x5B response (MD only).
    
    Parameters: BB (block number, >=2) CCx16 (16 bytes of title data).
    """

    block_number: int
    data: bytes
