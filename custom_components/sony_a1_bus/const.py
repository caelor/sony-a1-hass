"""Constants for the Sony A1 Bus integration."""

from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from .sensor import SonyA1BusLastMessageSensor

DOMAIN = "sony_a1_bus"

EVENT_SONY_A1_BUS_RX = "esphome.sony_a1_bus_rx"
EVENT_SONY_A1_BUS_HEARTBEAT = "esphome.sony_a1_bus_heartbeat"

ATTR_DATA = "data"
ATTR_TRUNCATED = "truncated"

SERVICE_DATA = "data"
CONF_MAX_RETRIES = "max_retries"

SERVICE_SET_MUSICBRAINZ_ID = "set_musicbrainz_id"
ATTR_MUSICBRAINZ_ID = "musicbrainz_id"

ESPHOME_DOMAIN = "esphome"
ESPHOME_SERVICE_TRANSMIT = "transmit"


# Address byte masks and bits
# Format: nnnnXyyy where nnnn=device type, X=direction (0=to, 1=from), yyy=sub-device
ADDRESS_DIRECTION_BIT = 0x08  # Bit 3: 0=to device, 1=from device
ADDRESS_SUBDEVICE_MASK = 0x07  # Bits 0-2: sub-device index
ADDRESS_TYPE_MASK = 0xF0  # Bits 4-7: device type


class DeviceType(IntEnum):
    """Device type codes from address byte upper nibble."""

    CD_PLAYER = 0x90
    MD_RECORDER = 0xB0
    AMPLIFIER = 0xC0
    TUNER = 0xC1
    SURROUND = 0xC3
    UNKNOWN = 0xFF


# Command bytes sent TO devices
class CommandType(IntEnum):
    """Command bytes sent TO devices."""
    CMD_PLAY = 0x00
    CMD_STOP = 0x01
    CMD_PAUSE = 0x02
    
    CMD_SKIP_NEXT = 0x08
    CMD_SKIP_PREVIOUS = 0x09

    CMD_SEND_TIME_UPDATES = 0x25

    QUERY_STATUS = 0x0F
    QUERY_CAPACITY = 0x22
    QUERY_DISC = 0x44
    QUERY_TRACK = 0x45
    QUERY_DISC_NAME = 0x58
    QUERY_TRACK_NAME = 0x5A
    QUERY_DEVICE_NAME = 0x6A


# Response bytes sent FROM devices
class ResponseType(IntEnum):
    """Response bytes sent FROM devices."""

    # Transport state
    PLAYING = 0x00
    STOPPED = 0x01
    PAUSED = 0x02
    EJECT = 0x03  # TOC Updated / Eject
    RECORD_PLAY = 0x04  # MD only
    RECORD_PAUSE_STATE = 0x07  # MD only
    DEVICE_READY = 0x08  # Device ready (disc loaded, ready to query disc info)
    TRACK_END_APPROACHING = 0x0C  # 30 seconds to end of track
    # Power state
    POWER_ON = 0x2E
    POWER_OFF = 0x2F
    # Disc/track data
    CD_TEXT_DETECTED = 0x47  # CD only - CD-TEXT disc detected
    TRACK_STATUS = 0x50
    TIME_UPDATE = 0x51
    DISC_LOADED = 0x58  # Loaded disc info (CD: DD only)
    DISC_TEXT_FIRST = 0x58  # MD: Disc text first block (DD 00 00 CCx14)
    DISC_TEXT_CONTINUATION = 0x59  # MD: Disc text continuation (BB CCx16)
    TRACK_TEXT_FIRST = 0x5A  # MD: Track text first block (TT 00 00 CCx14)
    TRACK_TEXT_CONTINUATION = 0x5B  # MD: Track text continuation (BB CCx16)
    DISC_INFO = 0x60
    DEVICE_CAPACITY = 0x61
    TRACK_INFO = 0x62
    DEVICE_NAME = 0x6A
    # Status
    STATUS = 0x70
    # Title errors
    NO_DISC_NAME = 0x16
    NO_TRACK_NAME = 0x17


# Transport state values from S1 byte in 0x70 status
class TransportState(IntEnum):
    """Transport state from status byte S1."""

    STOPPED = 0x00
    PLAYING = 0x01
    PAUSED = 0x02
    RECORDING = 0x04
    RECORD_PAUSE = 0x05


class TocState(StrEnum):
    """State of the Table of Contents reading."""

    COMPLETE = "Complete"
    LOADING = "Loading"
    INCOMPLETE = "Incomplete"


TOC_RETRY_TIMEOUT_SEC = 30
TOC_MAX_RETRIES = 3


class BridgeData(TypedDict):
    """Data structure for a Control-A1 bus bridge."""

    device_id: str
    node: str
    last_message: str
    truncated: bool
    sensor: "SonyA1BusLastMessageSensor | None"
    bridge_version: str
