"""Protocol decoder for Control-A1 bus messages.

Handles address byte decoding and message dispatch. Converts raw bytes into
typed Message objects using device-specific codecs.
"""

from dataclasses import dataclass

from ..const import (
    ADDRESS_DIRECTION_BIT,
    ADDRESS_SUBDEVICE_MASK,
    ADDRESS_TYPE_MASK,
    DeviceType,
    ResponseType,
    TransportState,
)
from .codec import BCDCodec, Codec, HexCodec
from .messages import (
    DeviceCapacityMessage,
    DeviceNameMessage,
    DiscInfoMessage,
    DiscLoadedMessage,
    DiscTextContinuationMessage,
    DiscTextFirstBlockMessage,
    Message,
    PowerMessage,
    StatusMessage,
    TimeUpdateMessage,
    TrackChangeMessage,
    TrackEndApproachingMessage,
    TrackInfoMessage,
    TrackTextContinuationMessage,
    TrackTextFirstBlockMessage,
    TransportMessage,
)


@dataclass
class AddressInfo:
    """Decoded address byte information."""

    device_type: DeviceType
    sub_index: int
    direction_from_device: bool
    canonical_address: int  # "to" address with direction bit cleared


def decode_address(address_byte: int) -> AddressInfo:
    """Decode the first byte of a bus message.

    Args:
        address_byte: The first byte of the message

    Returns:
        AddressInfo with decoded device type, sub-index, and direction
    """
    direction_from_device = bool(address_byte & ADDRESS_DIRECTION_BIT)
    sub_index = address_byte & ADDRESS_SUBDEVICE_MASK
    type_code = address_byte & ADDRESS_TYPE_MASK

    # Canonical address is the "to" address (direction bit cleared)
    canonical_address = address_byte & ~ADDRESS_DIRECTION_BIT

    # Map type code to DeviceType
    try:
        device_type = DeviceType(type_code)
    except ValueError:
        device_type = DeviceType.UNKNOWN

    return AddressInfo(
        device_type=device_type,
        sub_index=sub_index,
        direction_from_device=direction_from_device,
        canonical_address=canonical_address,
    )


def get_codec_for_device_type(device_type: DeviceType) -> Codec:
    """Get the appropriate codec for a device type.

    CD players use BCD encoding, MD players use raw hex.
    """
    if device_type == DeviceType.CD_PLAYER:
        return BCDCodec()
    elif device_type == DeviceType.MD_RECORDER:
        return HexCodec()
    else:
        # Default to hex for unknown device types
        return HexCodec()


def decode_message(
    address_info: AddressInfo,
    data: bytes,
    codec: Codec,
) -> Message | None:
    """Decode a bus message into a typed Message object.

    Args:
        address_info: Decoded address information
        data: Raw message bytes (including address byte)
        codec: Device-specific codec for decoding values

    Returns:
        Typed Message object, or None if message type is not recognized
    """
    if len(data) < 2:
        return None

    command = data[1]
    params = data[2:] if len(data) > 2 else b""

    # Universal messages (handled the same for all device types)
    if command == ResponseType.POWER_ON:
        return PowerMessage(command=command, raw_data=data, power_on=True)
    elif command == ResponseType.POWER_OFF:
        return PowerMessage(command=command, raw_data=data, power_on=False)
    elif command in (ResponseType.PLAYING, ResponseType.STOPPED, ResponseType.PAUSED):
        return TransportMessage(command=command, raw_data=data)
    elif command == ResponseType.TRACK_END_APPROACHING:
        return TrackEndApproachingMessage(command=command, raw_data=data)
    elif command == ResponseType.STATUS and len(params) >= 5:
        return _decode_status_message(command, data, params, codec)
    elif command == ResponseType.DISC_INFO and len(params) >= 6:
        return _decode_disc_info_message(command, data, params, codec)
    elif command == ResponseType.TRACK_INFO and len(params) >= 4:
        return _decode_track_info_message(command, data, params, codec)
    elif command == ResponseType.TRACK_STATUS and len(params) >= 4:
        return _decode_track_change_message(command, data, params, codec)
    elif command == ResponseType.TIME_UPDATE and len(params) >= 3:
        return _decode_time_update_message(command, data, params, codec, address_info)
    elif command == ResponseType.DEVICE_CAPACITY and len(params) >= 1:
        return _decode_device_capacity_message(command, data, params)
    elif command == ResponseType.DEVICE_NAME and len(params) >= 1:
        return _decode_device_name_message(command, data, params)
    elif command == ResponseType.DISC_LOADED and len(params) >= 1:
        if address_info.device_type == DeviceType.MD_RECORDER and len(params) >= 15:
            return _decode_disc_text_first_block(command, data, params, codec)
        return _decode_disc_loaded_message(command, data, params, codec)
    elif command == ResponseType.DISC_TEXT_CONTINUATION and len(params) >= 17:
        return _decode_disc_text_continuation(command, data, params)
    elif command == ResponseType.TRACK_TEXT_FIRST and len(params) >= 15:
        return _decode_track_text_first_block(command, data, params, codec)
    elif command == ResponseType.TRACK_TEXT_CONTINUATION and len(params) >= 17:
        return _decode_track_text_continuation(command, data, params)
    elif command in (ResponseType.NO_DISC_NAME, ResponseType.NO_TRACK_NAME):
        return Message(command=command, raw_data=data)

    # Unknown message type - return generic Message
    return Message(command=command, raw_data=data)


def _decode_status_message(
    command: int, data: bytes, params: bytes, codec: Codec
) -> StatusMessage:
    """Decode 0x70 status message."""
    s1, s2, s3, disc_byte, track_byte = params[:5]

    # Decode S1: transport state and power/disc flags
    transport_bits = s1 & 0x07  # Bits 0-2
    power_off = bool(s1 & 0x10)  # Bit 4
    disc_unloaded = bool(s1 & 0x20)  # Bit 5

    try:
        transport_state = TransportState(transport_bits)
    except ValueError:
        transport_state = TransportState.STOPPED

    # Decode S2: playback modes
    shuffle = bool(s2 & 0x01)  # Bit 0
    program = bool(s2 & 0x02)  # Bit 1
    repeat_all = bool(s2 & 0x08)  # Bit 3
    repeat_one = bool(s2 & 0x10)  # Bit 4

    # Decode S3: input source and mono
    input_bits = s3 & 0x07  # Bits 0-2
    if input_bits == 0x01:
        input_source = "Analog"
    elif input_bits == 0x03:
        input_source = "Optical"
    elif input_bits == 0x05:
        input_source = "Coax"
    else:
        input_source = "Unknown"
    mono = bool(s3 & 0x80)  # Bit 7

    # Decode disc and track numbers using codec
    disc_number = codec.decode_byte(disc_byte)
    track_number = codec.decode_byte(track_byte)

    return StatusMessage(
        command=command,
        raw_data=data,
        transport_state=transport_state,
        power_on=not power_off,
        disc_loaded=not disc_unloaded,
        shuffle=shuffle,
        program=program,
        repeat_all=repeat_all,
        repeat_one=repeat_one,
        disc_number=disc_number,
        track_number=track_number,
        input_source=input_source,
        mono=mono,
    )


def _decode_disc_info_message(
    command: int, data: bytes, params: bytes, codec: Codec
) -> DiscInfoMessage:
    """Decode 0x60 disc info message."""
    disc_byte, indexes, track_byte, mm_byte, ss_byte, frames = params[:6]

    return DiscInfoMessage(
        command=command,
        raw_data=data,
        disc_number=codec.decode_byte(disc_byte),
        indexes=indexes,
        track_count=codec.decode_byte(track_byte),
        total_minutes=codec.decode_byte(mm_byte),
        total_seconds=codec.decode_byte(ss_byte),
        frames=frames,
    )


def _decode_track_info_message(
    command: int, data: bytes, params: bytes, codec: Codec
) -> TrackInfoMessage:
    """Decode 0x62 track info message."""
    disc_byte, track_byte, mm_byte, ss_byte = params[:4]

    return TrackInfoMessage(
        command=command,
        raw_data=data,
        disc_number=codec.decode_byte(disc_byte),
        track_number=codec.decode_byte(track_byte),
        minutes=codec.decode_byte(mm_byte),
        seconds=codec.decode_byte(ss_byte),
    )


def _decode_track_change_message(
    command: int, data: bytes, params: bytes, codec: Codec
) -> TrackChangeMessage:
    """Decode 0x50 track change message."""
    disc_byte, track_byte, mm_byte, ss_byte = params[:4]

    return TrackChangeMessage(
        command=command,
        raw_data=data,
        disc_number=codec.decode_byte(disc_byte),
        track_number=codec.decode_byte(track_byte),
        minutes=codec.decode_byte(mm_byte),
        seconds=codec.decode_byte(ss_byte),
    )


def _decode_time_update_message(
    command: int,
    data: bytes,
    params: bytes,
    codec: Codec,
    address_info: AddressInfo,
) -> TimeUpdateMessage:
    """Decode 0x51 time update message.

    CD and MD have different formats:
    - CD: TT II MM SS (track, sub-track index, minutes, seconds)
    - MD: TT DD MM SS (track, disc, minutes, seconds)

    Time fields (MM, SS) are always BCD encoded regardless of device type.
    """
    bcd_codec = BCDCodec()

    if address_info.device_type == DeviceType.CD_PLAYER:
        # CD format: no disc number
        track_byte, _sub_index, mm_byte, ss_byte = params[:4]
        disc_number = None
    else:
        # MD format: includes disc number
        track_byte, disc_byte, mm_byte, ss_byte = params[:4]
        disc_number = codec.decode_byte(disc_byte)

    return TimeUpdateMessage(
        command=command,
        raw_data=data,
        track_number=codec.decode_byte(track_byte),
        disc_number=disc_number,
        minutes=bcd_codec.decode_byte(mm_byte),
        seconds=bcd_codec.decode_byte(ss_byte),
    )


def _decode_device_capacity_message(
    command: int, data: bytes, params: bytes
) -> DeviceCapacityMessage:
    """Decode 0x61 device capacity message."""
    disc_count = params[0]
    device_capabilities = None
    
    if len(params) > 1:
        device_capabilities = params[1]

    return DeviceCapacityMessage(
        command=command,
        raw_data=data,
        disc_count=disc_count,
        device_capabilities=device_capabilities,
    )


def _decode_device_name_message(
    command: int, data: bytes, params: bytes
) -> DeviceNameMessage:
    """Decode 0x6A device name message."""
    # Name is null-padded string
    name = params.rstrip(b"\x00").decode("ascii", errors="replace")

    return DeviceNameMessage(command=command, raw_data=data, name=name)


def _decode_disc_loaded_message(
    command: int, data: bytes, params: bytes, codec: Codec
) -> DiscLoadedMessage:
    """Decode 0x58 disc loaded message (CD only).
    
    CD format: DD (disc number, BCD encoded)
    """
    disc_byte = params[0]
    disc_number = codec.decode_byte(disc_byte)
    
    return DiscLoadedMessage(
        command=command,
        raw_data=data,
        disc_number=disc_number,
    )


def _decode_disc_text_first_block(
    command: int, data: bytes, params: bytes, codec: Codec
) -> DiscTextFirstBlockMessage:
    """Decode 0x58 disc text first block (MD only).
    
    MD format: DD 00 00 CCx14 (disc number + 14 bytes of title data)
    """
    disc_byte = params[0]
    disc_number = codec.decode_byte(disc_byte)
    title_fragment = params[3:17]
    
    return DiscTextFirstBlockMessage(
        command=command,
        raw_data=data,
        disc_number=disc_number,
        title_fragment=title_fragment,
    )


def _decode_disc_text_continuation(
    command: int, data: bytes, params: bytes
) -> DiscTextContinuationMessage:
    """Decode 0x59 disc text continuation block (MD only).
    
    Format: BB CCx16 (block number + 16 bytes of title data)
    """
    block_number = params[0]
    title_data = params[1:17]
    
    return DiscTextContinuationMessage(
        command=command,
        raw_data=data,
        block_number=block_number,
        data=title_data,
    )


def _decode_track_text_first_block(
    command: int, data: bytes, params: bytes, codec: Codec
) -> TrackTextFirstBlockMessage:
    """Decode 0x5A track text first block (MD only).
    
    Format: TT 00 00 CCx14 (track number + 14 bytes of title data)
    """
    track_byte = params[0]
    track_number = codec.decode_byte(track_byte)
    title_fragment = params[3:17]
    
    return TrackTextFirstBlockMessage(
        command=command,
        raw_data=data,
        track_number=track_number,
        title_fragment=title_fragment,
    )


def _decode_track_text_continuation(
    command: int, data: bytes, params: bytes
) -> TrackTextContinuationMessage:
    """Decode 0x5B track text continuation block (MD only).
    
    Format: BB CCx16 (block number + 16 bytes of title data)
    """
    block_number = params[0]
    title_data = params[1:17]
    
    return TrackTextContinuationMessage(
        command=command,
        raw_data=data,
        block_number=block_number,
        data=title_data,
    )
