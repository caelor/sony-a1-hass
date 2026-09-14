"""Tests for the protocol layer."""

import pytest

from custom_components.sony_a1_bus.const import DeviceType, TransportState
from custom_components.sony_a1_bus.protocol import (
    BCDCodec,
    HexCodec,
    decode_address,
    decode_message,
    get_codec_for_device_type,
)
from custom_components.sony_a1_bus.protocol.messages import (
    DeviceCapacityMessage,
    DeviceNameMessage,
    DiscInfoMessage,
    DiscLoadedMessage,
    PowerMessage,
    StatusMessage,
    TimeUpdateMessage,
    TrackChangeMessage,
    TrackEndApproachingMessage,
    TransportMessage,
)


class TestBCDCodec:
    """Tests for BCD codec."""

    def test_decode_zero(self):
        codec = BCDCodec()
        assert codec.decode_byte(0x00) == 0

    def test_decode_single_digit(self):
        codec = BCDCodec()
        assert codec.decode_byte(0x05) == 5

    def test_decode_double_digit(self):
        codec = BCDCodec()
        assert codec.decode_byte(0x45) == 45

    def test_decode_max(self):
        codec = BCDCodec()
        assert codec.decode_byte(0x99) == 99

    def test_encode_zero(self):
        codec = BCDCodec()
        assert codec.encode_byte(0) == 0x00

    def test_encode_single_digit(self):
        codec = BCDCodec()
        assert codec.encode_byte(5) == 0x05

    def test_encode_double_digit(self):
        codec = BCDCodec()
        assert codec.encode_byte(45) == 0x45

    def test_encode_max(self):
        codec = BCDCodec()
        assert codec.encode_byte(99) == 0x99


class TestHexCodec:
    """Tests for hex codec."""

    def test_decode_passthrough(self):
        codec = HexCodec()
        assert codec.decode_byte(0x45) == 0x45
        assert codec.decode_byte(0x00) == 0x00
        assert codec.decode_byte(0xFF) == 0xFF

    def test_encode_passthrough(self):
        codec = HexCodec()
        assert codec.encode_byte(0x45) == 0x45


class TestDecodeAddress:
    """Tests for address byte decoding."""

    def test_cd_player_from_device(self):
        # 0x98 = 1001 1000: CD player (0x9), direction=from (1), sub=0
        info = decode_address(0x98)
        assert info.device_type == DeviceType.CD_PLAYER
        assert info.direction_from_device is True
        assert info.sub_index == 0
        assert info.canonical_address == 0x90

    def test_cd_player_to_device(self):
        # 0x90 = 1001 0000: CD player (0x9), direction=to (0), sub=0
        info = decode_address(0x90)
        assert info.device_type == DeviceType.CD_PLAYER
        assert info.direction_from_device is False
        assert info.sub_index == 0
        assert info.canonical_address == 0x90

    def test_md_recorder_with_sub_index(self):
        # 0xB9 = 1011 1001: MD recorder (0xB), direction=from (1), sub=1
        info = decode_address(0xB9)
        assert info.device_type == DeviceType.MD_RECORDER
        assert info.direction_from_device is True
        assert info.sub_index == 1
        assert info.canonical_address == 0xB1

    def test_amplifier(self):
        # 0xC8 = 1100 1000: Amplifier (0xC), direction=from (1), sub=0
        info = decode_address(0xC8)
        assert info.device_type == DeviceType.AMPLIFIER
        assert info.direction_from_device is True
        assert info.sub_index == 0

    def test_unknown_device_type(self):
        # 0x18 = 0001 1000: Unknown type (0x1), direction=from (1), sub=0
        info = decode_address(0x18)
        assert info.device_type == DeviceType.UNKNOWN
        assert info.direction_from_device is True
        assert info.sub_index == 0


class TestGetCodecForDeviceType:
    """Tests for codec selection."""

    def test_cd_player_gets_bcd_codec(self):
        codec = get_codec_for_device_type(DeviceType.CD_PLAYER)
        assert isinstance(codec, BCDCodec)

    def test_md_recorder_gets_hex_codec(self):
        codec = get_codec_for_device_type(DeviceType.MD_RECORDER)
        assert isinstance(codec, HexCodec)

    def test_unknown_gets_hex_codec(self):
        codec = get_codec_for_device_type(DeviceType.UNKNOWN)
        assert isinstance(codec, HexCodec)


class TestDecodeMessage:
    """Tests for message decoding."""

    def test_power_on_message(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        data = bytes([0x98, 0x2E])  # CD player, power on
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, PowerMessage)
        assert msg.power_on is True

    def test_power_off_message(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        data = bytes([0x98, 0x2F])  # CD player, power off
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, PowerMessage)
        assert msg.power_on is False

    def test_transport_play_message(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        data = bytes([0x98, 0x00])  # CD player, play
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, TransportMessage)
        assert msg.command == 0x00

    def test_status_message_bcd(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        # Status: playing, shuffle on, disc 1, track 5 (BCD)
        data = bytes([0x98, 0x70, 0x01, 0x01, 0x00, 0x01, 0x05])
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, StatusMessage)
        assert msg.transport_state == TransportState.PLAYING
        assert msg.power_on is True
        assert msg.disc_loaded is True
        assert msg.shuffle is True
        assert msg.disc_number == 1
        assert msg.track_number == 5

    def test_status_message_hex(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # Status: paused, repeat all on, disc 1, track 10 (hex)
        data = bytes([0xB8, 0x70, 0x02, 0x08, 0x00, 0x01, 0x0A])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, StatusMessage)
        assert msg.transport_state == TransportState.PAUSED
        assert msg.repeat_all is True
        assert msg.disc_number == 1
        assert msg.track_number == 10  # 0x0A = 10 in hex

    def test_status_message_s3_analog_input(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # Status: S3=0x01 (analog input)
        data = bytes([0xB8, 0x70, 0x01, 0x00, 0x01, 0x01, 0x01])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, StatusMessage)
        assert msg.input_source == "Analog"
        assert msg.mono is False

    def test_status_message_s3_optical_input(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # Status: S3=0x03 (optical input)
        data = bytes([0xB8, 0x70, 0x01, 0x00, 0x03, 0x01, 0x01])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, StatusMessage)
        assert msg.input_source == "Optical"

    def test_status_message_s3_coax_input(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # Status: S3=0x05 (coax input)
        data = bytes([0xB8, 0x70, 0x01, 0x00, 0x05, 0x01, 0x01])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, StatusMessage)
        assert msg.input_source == "Coax"

    def test_status_message_s3_unknown_input(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # Status: S3=0x00 (unknown input)
        data = bytes([0xB8, 0x70, 0x01, 0x00, 0x00, 0x01, 0x01])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, StatusMessage)
        assert msg.input_source == "Unknown"

    def test_status_message_s3_mono_flag(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # Status: S3=0x81 (analog input + mono flag)
        data = bytes([0xB8, 0x70, 0x01, 0x00, 0x81, 0x01, 0x01])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, StatusMessage)
        assert msg.input_source == "Analog"
        assert msg.mono is True

    def test_disc_info_message_bcd(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        # Disc info: disc 1, 1 index, 12 tracks, 45:30 total, 0 frames
        data = bytes([0x98, 0x60, 0x01, 0x01, 0x12, 0x45, 0x30, 0x00])
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DiscInfoMessage)
        assert msg.disc_number == 1
        assert msg.track_count == 12
        assert msg.total_minutes == 45
        assert msg.total_seconds == 30

    def test_disc_info_message_hex(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # Disc info: disc 1, 1 index, 20 tracks (0x14), 74:00 total (0x4A:0x00), 0 frames
        data = bytes([0xB8, 0x60, 0x01, 0x01, 0x14, 0x4A, 0x00, 0x00])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DiscInfoMessage)
        assert msg.disc_number == 1
        assert msg.track_count == 20  # 0x14 = 20 in hex
        assert msg.total_minutes == 74  # 0x4A = 74 in hex
        assert msg.total_seconds == 0

    def test_track_change_message(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        # Track change: disc 1, track 3, 2:45 duration
        data = bytes([0x98, 0x50, 0x01, 0x03, 0x02, 0x45])
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, TrackChangeMessage)
        assert msg.disc_number == 1
        assert msg.track_number == 3
        assert msg.minutes == 2
        assert msg.seconds == 45

    def test_time_update_message_md_uses_bcd_for_time(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # MD time update: track 5 (hex 0x05), disc 2 (hex 0x02), 1:25 position
        # MM=0x12 BCD=12, SS=0x25 BCD=25 -> 12:25
        data = bytes([0xB8, 0x51, 0x05, 0x02, 0x12, 0x25])
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, TimeUpdateMessage)
        assert msg.track_number == 5  # Hex codec for track
        assert msg.disc_number == 2  # Hex codec for disc
        assert msg.minutes == 12  # BCD codec for time: 0x12 -> 12
        assert msg.seconds == 25  # BCD codec for time: 0x25 -> 25

    def test_device_capacity_message(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        # Device capacity: 5 discs, device ID 0x20
        data = bytes([0x98, 0x61, 0x05, 0x20])
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DeviceCapacityMessage)
        assert msg.disc_count == 5
        assert msg.device_capabilities == 0x20

    def test_device_name_message(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        # Device name: "CDP-XE520" null-padded to 17 bytes
        name_bytes = b"CDP-XE520" + b"\x00" * 8
        data = bytes([0x98, 0x6A]) + name_bytes
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DeviceNameMessage)
        assert msg.name == "CDP-XE520"

    def test_track_end_approaching_message_cd(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        data = bytes([0x98, 0x0C])  # CD player, track end approaching
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, TrackEndApproachingMessage)
        assert msg.command == 0x0C

    def test_track_end_approaching_message_md(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        data = bytes([0xB8, 0x0C])  # MD player, track end approaching
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, TrackEndApproachingMessage)
        assert msg.command == 0x0C

    def test_short_message_returns_none(self):
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        data = bytes([0x98])  # Only address byte
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert msg is None

    def test_disc_loaded_message_cd_type(self):
        """Test decoding 0x58 CD type (single DD param)."""
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        # CD type: just disc number (BCD encoded)
        data = bytes([0x98, 0x58, 0x01])  # Disc 1
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DiscLoadedMessage)
        assert msg.disc_number == 1

    def test_disc_loaded_message_cd_type_disc_2(self):
        """Test decoding 0x58 CD type with disc number 2."""
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo

        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        # CD type: disc 2 (BCD encoded)
        data = bytes([0x98, 0x58, 0x02])
        codec = BCDCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DiscLoadedMessage)
        assert msg.disc_number == 2

    def test_disc_text_first_block_md_type(self):
        """Test decoding 0x58 MD type as disc text first block."""
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo
        from custom_components.sony_a1_bus.protocol.messages import DiscTextFirstBlockMessage

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # MD type: disc number + 0x00 + 0x00 + 14 bytes of title
        # Disc 1, title "Test Album" (14 bytes, padded with 0x00)
        title = b"Test Album" + b"\x00" * 4
        data = bytes([0xB8, 0x58, 0x01, 0x00, 0x00]) + title
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DiscTextFirstBlockMessage)
        assert msg.disc_number == 1
        assert msg.title_fragment == title

    def test_disc_text_first_block_md_type_different_disc(self):
        """Test decoding 0x58 MD type with different disc number."""
        from custom_components.sony_a1_bus.protocol.decoder import AddressInfo
        from custom_components.sony_a1_bus.protocol.messages import DiscTextFirstBlockMessage

        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        # MD type: disc 10 (0x0A hex)
        title = b"\x00" * 14  # Empty title
        data = bytes([0xB8, 0x58, 0x0A, 0x00, 0x00]) + title
        codec = HexCodec()

        msg = decode_message(address_info, data, codec)
        assert isinstance(msg, DiscTextFirstBlockMessage)
        assert msg.disc_number == 10  # Hex codec, so 0x0A = 10
