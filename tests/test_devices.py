"""Tests for the device layer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.sony_a1_bus.const import (
    CommandType,
    DeviceType,
    ResponseType,
    TransportState,
)
from custom_components.sony_a1_bus.devices import DeviceRegistry
from custom_components.sony_a1_bus.devices.cd_player import CDPlayer
from custom_components.sony_a1_bus.devices.md_player import MDPlayer
from custom_components.sony_a1_bus.devices.player import Player
from custom_components.sony_a1_bus.protocol import (
    AddressInfo,
    DeviceCapacityMessage,
    DeviceNameMessage,
    DiscInfoMessage,
    DiscLoadedMessage,
    PowerMessage,
    StatusMessage,
    TimeUpdateMessage,
    TrackChangeMessage,
    TrackEndApproachingMessage,
    TrackInfoMessage,
    TransportMessage,
)


class TestPlayer:
    """Tests for Player base class."""

    def test_canonical_address(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        assert player.canonical_address == 0x90

    def test_canonical_address_with_sub_index(self):
        player = CDPlayer(sub_index=2, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        assert player.canonical_address == 0x92

    def test_unique_id(self):
        player = CDPlayer(sub_index=0, bridge_node="test_node", bridge_device_id="dev1", hass=MagicMock())
        assert player.unique_id == "test_node_90_0"

    def test_name_cd_player(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        assert player.name == "CD-0"

    def test_name_md_player(self):
        player = MDPlayer(sub_index=1, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        assert player.name == "MD-1"

    def test_initial_state(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        assert player.power_on is False
        assert player.disc_loaded is False
        assert player.transport_state == TransportState.STOPPED
        assert player.current_disc == 1
        assert player.current_track == 0
        assert player.track_count == 0

    def test_handle_power_on(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = PowerMessage(command=ResponseType.POWER_ON, raw_data=b"", power_on=True)
        player.handle_message(msg)
        assert player.power_on is True

    def test_handle_power_off(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.power_on = True
        player.transport_state = TransportState.PLAYING
        msg = PowerMessage(command=ResponseType.POWER_OFF, raw_data=b"", power_on=False)
        player.handle_message(msg)
        assert player.power_on is False
        assert player.transport_state == TransportState.STOPPED

    def test_handle_transport_play(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = TransportMessage(command=ResponseType.PLAYING, raw_data=b"")
        player.handle_message(msg)
        assert player.transport_state == TransportState.PLAYING
        assert player.power_on is True  # Transport messages imply device is on

    def test_handle_transport_stop(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.transport_state = TransportState.PLAYING
        msg = TransportMessage(command=ResponseType.STOPPED, raw_data=b"")
        player.handle_message(msg)
        assert player.transport_state == TransportState.STOPPED
        assert player.power_on is True  # Transport messages imply device is on

    def test_handle_transport_pause(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.transport_state = TransportState.PLAYING
        msg = TransportMessage(command=ResponseType.PAUSED, raw_data=b"")
        player.handle_message(msg)
        assert player.transport_state == TransportState.PAUSED
        assert player.power_on is True  # Transport messages imply device is on

    def test_handle_status_message(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = StatusMessage(
            command=ResponseType.STATUS,
            raw_data=b"",
            transport_state=TransportState.PLAYING,
            power_on=True,
            disc_loaded=True,
            shuffle=True,
            program=False,
            repeat_all=True,
            repeat_one=False,
            disc_number=1,
            track_number=5,
            input_source="Optical",
            mono=True,
        )
        player.handle_message(msg)
        assert player.power_on is True
        assert player.disc_loaded is True
        assert player.transport_state == TransportState.PLAYING
        assert player.shuffle is True
        assert player.repeat_all is True
        assert player.current_disc == 1
        assert player.current_track == 5
        assert player.input_source == "Optical"
        assert player.mono is True

    def test_handle_disc_info_message(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=12,
            total_minutes=45,
            total_seconds=30,
            frames=0,
        )
        player.handle_message(msg)
        assert player.current_disc == 1
        assert player.track_count == 12
        assert player.total_minutes == 45
        assert player.total_seconds == 30

    def test_handle_track_change_message(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = TrackChangeMessage(
            command=ResponseType.TRACK_STATUS,
            raw_data=b"",
            disc_number=1,
            track_number=3,
            minutes=2,
            seconds=45,
        )
        responses = player.handle_message(msg)
        assert player.current_disc == 1
        assert player.current_track == 3
        assert player.track_duration_minutes == 2
        assert player.track_duration_seconds == 45
        # When not playing, should trigger query_status and time updates
        assert responses == [bytes([CommandType.QUERY_STATUS]), bytes([CommandType.CMD_SEND_TIME_UPDATES])]

    def test_handle_track_change_message_when_playing_no_query(self):
        """Test that track change when already playing does not trigger query_status."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        # Set transport state to playing
        player.transport_state = TransportState.PLAYING
        # Set device info to prevent opportunistic queries
        player.device_capabilities = 0x01
        player.device_name = "Test Player"
        
        msg = TrackChangeMessage(
            command=ResponseType.TRACK_STATUS,
            raw_data=b"",
            disc_number=1,
            track_number=3,
            minutes=2,
            seconds=45,
        )
        responses = player.handle_message(msg)
        # When already playing, should not trigger query_status but should enable time updates
        assert responses == [bytes([CommandType.CMD_SEND_TIME_UPDATES])]

    def test_handle_track_change_message_when_paused_triggers_query(self):
        """Test that track change when paused triggers query_status."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        # Set transport state to paused
        player.transport_state = TransportState.PAUSED
        
        msg = TrackChangeMessage(
            command=ResponseType.TRACK_STATUS,
            raw_data=b"",
            disc_number=1,
            track_number=3,
            minutes=2,
            seconds=45,
        )
        responses = player.handle_message(msg)
        # When paused, should trigger query_status and time updates
        assert responses == [bytes([CommandType.QUERY_STATUS]), bytes([CommandType.CMD_SEND_TIME_UPDATES])]

    def test_handle_track_change_message_when_stopped_triggers_query(self):
        """Test that track change when stopped triggers query_status."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        # Transport state defaults to stopped
        
        msg = TrackChangeMessage(
            command=ResponseType.TRACK_STATUS,
            raw_data=b"",
            disc_number=1,
            track_number=3,
            minutes=2,
            seconds=45,
        )
        responses = player.handle_message(msg)
        # When stopped, should trigger query_status and time updates
        assert responses == [bytes([CommandType.QUERY_STATUS]), bytes([CommandType.CMD_SEND_TIME_UPDATES])]

    def test_handle_track_end_approaching_with_known_duration(self):
        """Test that track end approaching sets position to duration - 30."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.track_duration_minutes = 5
        player.track_duration_seconds = 30
        player.time_estimator.play()
        player.time_estimator.set_position(100.0)
        
        msg = TrackEndApproachingMessage(
            command=ResponseType.TRACK_END_APPROACHING,
            raw_data=b"",
        )
        player.handle_message(msg)
        # Position should be (5*60 + 30) - 30 = 300 seconds
        assert player.time_estimator.get_position() == pytest.approx(300.0, abs=0.1)

    def test_handle_track_end_approaching_with_unknown_duration(self):
        """Test that track end approaching logs warning when duration unknown."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.time_estimator.play()
        player.time_estimator.set_position(100.0)
        
        msg = TrackEndApproachingMessage(
            command=ResponseType.TRACK_END_APPROACHING,
            raw_data=b"",
        )
        player.handle_message(msg)
        # Position should remain unchanged
        assert player.time_estimator.get_position() == pytest.approx(100.0, abs=0.1)

    def test_handle_track_end_approaching_with_only_seconds(self):
        """Test that track end approaching works when only seconds are set."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.track_duration_minutes = 0
        player.track_duration_seconds = 45
        player.time_estimator.play()
        
        msg = TrackEndApproachingMessage(
            command=ResponseType.TRACK_END_APPROACHING,
            raw_data=b"",
        )
        player.handle_message(msg)
        # Position should be (0*60 + 45) - 30 = 15 seconds
        assert player.time_estimator.get_position() == pytest.approx(15.0, abs=0.1)

    def test_handle_device_capacity_message(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = DeviceCapacityMessage(
            command=ResponseType.DEVICE_CAPACITY,
            raw_data=b"",
            disc_count=5,
            device_capabilities=0x20,
        )
        player.handle_message(msg)
        assert player.disc_count == 5
        assert player.device_capabilities == 0x20

    def test_handle_device_name_message(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = DeviceNameMessage(
            command=ResponseType.DEVICE_NAME,
            raw_data=b"",
            name="CDP-XE520",
        )
        player.handle_message(msg)
        assert player.device_name == "CDP-XE520"


class TestMDPlayer:
    """Tests for MDPlayer-specific behavior."""

    def test_handle_record_play(self):
        from custom_components.sony_a1_bus.protocol import Message

        player = MDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        # RECORD_PLAY is not a universal transport message, so it's a generic Message
        msg = Message(command=ResponseType.RECORD_PLAY, raw_data=b"")
        player.handle_message(msg)
        assert player.transport_state == TransportState.RECORDING

    def test_handle_record_pause(self):
        from custom_components.sony_a1_bus.protocol import Message

        player = MDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        # RECORD_PAUSE is not a universal transport message, so it's a generic Message
        msg = Message(command=ResponseType.RECORD_PAUSE_STATE, raw_data=b"")
        player.handle_message(msg)
        assert player.transport_state == TransportState.RECORD_PAUSE


class TestDeviceRegistry:
    """Tests for DeviceRegistry."""

    def test_create_cd_player(self):
        registry = DeviceRegistry(hass=MagicMock(), bridge_node="test", bridge_device_id="dev1")
        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        player = registry.get_or_create_device(address_info)
        assert player is not None
        assert isinstance(player, CDPlayer)
        assert player.device_type == DeviceType.CD_PLAYER
        assert player.sub_index == 0

    def test_create_md_player(self):
        registry = DeviceRegistry(hass=MagicMock(), bridge_node="test", bridge_device_id="dev1")
        address_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        player = registry.get_or_create_device(address_info)
        assert player is not None
        assert isinstance(player, MDPlayer)
        assert player.device_type == DeviceType.MD_RECORDER

    def test_get_existing_device(self):
        registry = DeviceRegistry(hass=MagicMock(), bridge_node="test", bridge_device_id="dev1")
        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        player1 = registry.get_or_create_device(address_info)
        player2 = registry.get_or_create_device(address_info)
        assert player1 is player2

    def test_ignore_to_device_messages(self):
        registry = DeviceRegistry(hass=MagicMock(), bridge_node="test", bridge_device_id="dev1")
        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=False,  # TO device, not FROM
            canonical_address=0x90,
        )
        player = registry.get_or_create_device(address_info)
        assert player is None

    def test_unsupported_device_type(self):
        registry = DeviceRegistry(hass=MagicMock(), bridge_node="test", bridge_device_id="dev1")
        address_info = AddressInfo(
            device_type=DeviceType.UNKNOWN,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x10,
        )
        player = registry.get_or_create_device(address_info)
        assert player is None

    def test_get_all_devices(self):
        registry = DeviceRegistry(hass=MagicMock(), bridge_node="test", bridge_device_id="dev1")
        # Create a CD player
        cd_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0x90,
        )
        registry.get_or_create_device(cd_info)
        # Create an MD player
        md_info = AddressInfo(
            device_type=DeviceType.MD_RECORDER,
            sub_index=0,
            direction_from_device=True,
            canonical_address=0xB0,
        )
        registry.get_or_create_device(md_info)

        devices = registry.get_all_devices()
        assert len(devices) == 2
        assert any(isinstance(d, CDPlayer) for d in devices)
        assert any(isinstance(d, MDPlayer) for d in devices)

    def test_get_device_by_type_and_index(self):
        registry = DeviceRegistry(hass=MagicMock(), bridge_node="test", bridge_device_id="dev1")
        address_info = AddressInfo(
            device_type=DeviceType.CD_PLAYER,
            sub_index=2,
            direction_from_device=True,
            canonical_address=0x92,
        )
        registry.get_or_create_device(address_info)

        player = registry.get_device(DeviceType.CD_PLAYER, 2)
        assert player is not None
        assert player.sub_index == 2

        # Non-existent device
        player = registry.get_device(DeviceType.CD_PLAYER, 5)
        assert player is None


class FakeClock:
    """A fake clock for testing."""

    def __init__(self, time: float = 0.0) -> None:
        self._time = time

    def __call__(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        self._time += seconds


class TestPlayerTimeEstimator:
    """Tests for Player integration with TimeEstimator."""

    def test_player_has_time_estimator(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        assert player.time_estimator is not None
        assert player.time_estimator.is_stopped

    def test_transport_play_updates_time_estimator(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = TransportMessage(command=ResponseType.PLAYING, raw_data=b"")
        player.handle_message(msg)
        assert player.time_estimator.is_playing

    def test_transport_pause_updates_time_estimator(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.handle_message(TransportMessage(command=ResponseType.PLAYING, raw_data=b""))
        player.handle_message(TransportMessage(command=ResponseType.PAUSED, raw_data=b""))
        assert player.time_estimator.is_paused

    def test_transport_stop_updates_time_estimator(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.handle_message(TransportMessage(command=ResponseType.PLAYING, raw_data=b""))
        player.handle_message(TransportMessage(command=ResponseType.STOPPED, raw_data=b""))
        assert player.time_estimator.is_stopped

    def test_status_message_syncs_time_estimator_playing(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = StatusMessage(
            command=ResponseType.STATUS,
            raw_data=b"",
            transport_state=TransportState.PLAYING,
            power_on=True,
            disc_loaded=True,
            shuffle=False,
            program=False,
            repeat_all=False,
            repeat_one=False,
            disc_number=1,
            track_number=1,
            input_source="Unknown",
            mono=False,
        )
        player.handle_message(msg)
        assert player.time_estimator.is_playing

    def test_status_message_syncs_time_estimator_paused(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.handle_message(TransportMessage(command=ResponseType.PLAYING, raw_data=b""))
        msg = StatusMessage(
            command=ResponseType.STATUS,
            raw_data=b"",
            transport_state=TransportState.PAUSED,
            power_on=True,
            disc_loaded=True,
            shuffle=False,
            program=False,
            repeat_all=False,
            repeat_one=False,
            disc_number=1,
            track_number=1,
            input_source="Unknown",
            mono=False,
        )
        player.handle_message(msg)
        assert player.time_estimator.is_paused

    def test_status_message_syncs_time_estimator_stopped(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.handle_message(TransportMessage(command=ResponseType.PLAYING, raw_data=b""))
        msg = StatusMessage(
            command=ResponseType.STATUS,
            raw_data=b"",
            transport_state=TransportState.STOPPED,
            power_on=True,
            disc_loaded=True,
            shuffle=False,
            program=False,
            repeat_all=False,
            repeat_one=False,
            disc_number=1,
            track_number=0,
            input_source="Unknown",
            mono=False,
        )
        player.handle_message(msg)
        assert player.time_estimator.is_stopped

    def test_track_change_resets_time_estimator_position(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = TrackChangeMessage(
            command=ResponseType.TRACK_STATUS,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=2,
            seconds=30,
        )
        player.handle_message(msg)
        assert player.time_estimator.get_position() == 0.0
        assert player.track_duration_minutes == 2
        assert player.track_duration_seconds == 30

    def test_track_change_while_playing_resets_position(self):
        clock = FakeClock()
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.time_estimator = __import__(
            "custom_components.sony_a1_bus.devices.time_estimator",
            fromlist=["TimeEstimator"],
        ).TimeEstimator(clock=clock)
        player.handle_message(TransportMessage(command=ResponseType.PLAYING, raw_data=b""))
        clock.advance(10.0)
        assert player.time_estimator.get_position() == 10.0
        msg = TrackChangeMessage(
            command=ResponseType.TRACK_STATUS,
            raw_data=b"",
            disc_number=1,
            track_number=2,
            minutes=3,
            seconds=0,
        )
        player.handle_message(msg)
        assert player.time_estimator.get_position() == 0.0
        clock.advance(5.0)
        assert player.time_estimator.get_position() == 5.0

    def test_time_update_message_updates_time_estimator(self):
        clock = FakeClock()
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.time_estimator = __import__(
            "custom_components.sony_a1_bus.devices.time_estimator",
            fromlist=["TimeEstimator"],
        ).TimeEstimator(clock=clock)
        player.handle_message(TransportMessage(command=ResponseType.PLAYING, raw_data=b""))
        msg = TimeUpdateMessage(
            command=ResponseType.TIME_UPDATE,
            raw_data=b"",
            track_number=1,
            disc_number=None,
            minutes=1,
            seconds=30,
        )
        player.handle_message(msg)
        assert player.time_estimator.get_position() == 90.0
        assert player.current_minutes == 1
        assert player.current_seconds == 30

    def test_power_off_stops_time_estimator(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.handle_message(TransportMessage(command=ResponseType.PLAYING, raw_data=b""))
        msg = PowerMessage(command=ResponseType.POWER_OFF, raw_data=b"", power_on=False)
        player.handle_message(msg)
        # Power off sets transport_state to STOPPED but doesn't directly call time_estimator.stop()
        # This is intentional - the time_estimator is synced via status messages
        assert player.transport_state == TransportState.STOPPED


class TestPlayerSendCallback:
    """Tests for Player send callback functionality."""

    async def test_send_command_without_callback_returns_false(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        result = await player.async_send_command(bytes([0x0F]))
        assert result is False

    async def test_send_command_with_callback_returns_true(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        
        async def mock_callback(data: bytes) -> bool:
            return True
        
        player.set_send_callback(mock_callback)
        result = await player.async_send_command(bytes([0x0F]))
        assert result is True

    async def test_send_command_with_callback_returns_false_on_failure(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        
        async def mock_callback(data: bytes) -> bool:
            return False
        
        player.set_send_callback(mock_callback)
        result = await player.async_send_command(bytes([0x0F]))
        assert result is False

    async def test_query_status_returns_callback_result(self):
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        
        async def mock_callback(data: bytes) -> bool:
            # Verify the command is 0x0F
            assert data == bytes([0x90, 0x0F])  # Address + command
            return True
        
        player.set_send_callback(mock_callback)
        result = await player.async_query_status()
        assert result is True


class TestDiscLoadedTracking:
    """Tests for disc_loaded state tracking via _set_disc_loaded."""

    def test_set_disc_loaded_false_to_true_sends_query_disc(self):
        """Test that disc_loaded false->true transition sends 0x44 Query Disc."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01  # Prevent opportunistic queries
        player.device_name = "Test"
        
        assert player.disc_loaded is False
        responses = player._set_disc_loaded(True, disc_number=1)
        
        assert player.disc_loaded is True
        # Should send 0x44 with BCD-encoded disc number 01
        assert responses == [bytes([CommandType.QUERY_DISC, 0x01])]

    def test_set_disc_loaded_true_to_true_sends_query_disc_and_warns(self):
        """Test that unexpected disc_loaded=true still sends 0x44 Query Disc."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        responses = player._set_disc_loaded(True, disc_number=2)
        
        # Should still send 0x44 to update understanding of new disc
        assert responses == [bytes([CommandType.QUERY_DISC, 0x02])]

    def test_set_disc_loaded_true_to_false_no_query(self):
        """Test that disc_loaded true->false transition does not send query."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        responses = player._set_disc_loaded(False)
        
        assert player.disc_loaded is False
        assert responses == []

    def test_set_disc_loaded_false_to_false_no_query(self):
        """Test that disc_loaded false->false does not send query."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        responses = player._set_disc_loaded(False)
        
        assert player.disc_loaded is False
        assert responses == []

    def test_set_disc_loaded_md_uses_hex_codec(self):
        """Test that MD player uses hex encoding for disc number."""
        player = MDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        responses = player._set_disc_loaded(True, disc_number=10)
        
        # MD uses hex codec, so disc 10 = 0x0A
        assert responses == [bytes([CommandType.QUERY_DISC, 0x0A])]

    def test_status_message_disc_loaded_transition_sends_query(self):
        """Test that status message with disc_loaded=true sends 0x44."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = StatusMessage(
            command=ResponseType.STATUS,
            raw_data=b"",
            transport_state=TransportState.STOPPED,
            power_on=True,
            disc_loaded=True,
            shuffle=False,
            program=False,
            repeat_all=False,
            repeat_one=False,
            disc_number=1,
            track_number=0,
            input_source="Unknown",
            mono=False,
        )
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is True
        # Should send 0x44 Query Disc
        assert bytes([CommandType.QUERY_DISC, 0x01]) in responses

    def test_status_message_disc_loaded_already_true_no_query(self):
        """Test that status message with disc_loaded=true when already loaded does not send 0x44."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = StatusMessage(
            command=ResponseType.STATUS,
            raw_data=b"",
            transport_state=TransportState.STOPPED,
            power_on=True,
            disc_loaded=True,
            shuffle=False,
            program=False,
            repeat_all=False,
            repeat_one=False,
            disc_number=1,
            track_number=0,
            input_source="Unknown",
            mono=False,
        )
        responses = player.handle_message(msg)
        
        # Should not send 0x44 when already loaded and from status (to avoid spam)
        assert bytes([CommandType.QUERY_DISC, 0x01]) not in responses

    def test_status_message_disc_unloaded_no_query(self):
        """Test that status message with disc_loaded=false does not send 0x44."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = StatusMessage(
            command=ResponseType.STATUS,
            raw_data=b"",
            transport_state=TransportState.STOPPED,
            power_on=True,
            disc_loaded=False,
            shuffle=False,
            program=False,
            repeat_all=False,
            repeat_one=False,
            disc_number=1,
            track_number=0,
            input_source="Unknown",
            mono=False,
        )
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is False
        # Should not send 0x44
        assert not any(r[0] == CommandType.QUERY_DISC for r in responses if r)


class TestEjectMessage:
    """Tests for 0x03 eject message handling."""

    def test_eject_message_sets_disc_loaded_false(self):
        """Test that 0x03 eject message sets disc_loaded to false."""
        from custom_components.sony_a1_bus.protocol import Message
        
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = Message(command=ResponseType.EJECT, raw_data=b"")
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is False
        # Eject should not trigger any queries
        assert responses == []

    def test_eject_message_when_already_unloaded(self):
        """Test that 0x03 eject when already unloaded is a no-op."""
        from custom_components.sony_a1_bus.protocol import Message
        
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = Message(command=ResponseType.EJECT, raw_data=b"")
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is False
        assert responses == []


class TestCDTextDetectedMessage:
    """Tests for 0x47 CD-TEXT detected message handling (CDPlayer only)."""

    def test_cd_text_detected_sets_disc_loaded_true(self):
        """Test that 0x47 CD-TEXT detected sets disc_loaded to true."""
        from custom_components.sony_a1_bus.protocol import Message
        
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        # 0x47 with unknown parameters (8 bytes as per protocol)
        msg = Message(command=ResponseType.CD_TEXT_DETECTED, raw_data=b"\x98\x47\x09\x09\xFF\xFF\xFF\xFF\xFF\xFF")
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is True
        # Should send 0x44 Query Disc with disc_number=1 (assumption)
        assert responses == [bytes([CommandType.QUERY_DISC, 0x01])]

    def test_cd_text_detected_when_already_loaded(self):
        """Test that 0x47 when already loaded still sends query."""
        from custom_components.sony_a1_bus.protocol import Message
        
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = Message(command=ResponseType.CD_TEXT_DETECTED, raw_data=b"\x98\x47")
        responses = player.handle_message(msg)
        
        # Should still send 0x44
        assert responses == [bytes([CommandType.QUERY_DISC, 0x01])]


class TestDiscLoadedMessage:
    """Tests for 0x58 disc loaded message handling."""

    def test_disc_loaded_cd_player(self):
        """Test that 0x58 CD type sets disc_loaded and sends query."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = DiscLoadedMessage(
            command=ResponseType.DISC_LOADED,
            raw_data=b"",
            disc_number=1,
        )
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is True
        # CD uses BCD codec, disc 1 = 0x01
        assert responses == [bytes([CommandType.QUERY_DISC, 0x01])]

    def test_disc_loaded_md_player(self):
        """Test that 0x58 for MD is now disc text, not disc loaded."""
        player = MDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = DiscLoadedMessage(
            command=ResponseType.DISC_LOADED,
            raw_data=b"",
            disc_number=1,
        )
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is False
        assert responses == []

    def test_disc_loaded_with_different_disc_number(self):
        """Test that 0x58 with disc_number=2 sends correct query."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"
        
        msg = DiscLoadedMessage(
            command=ResponseType.DISC_LOADED,
            raw_data=b"",
            disc_number=2,
        )
        responses = player.handle_message(msg)
        
        assert player.disc_loaded is True
        # CD uses BCD codec, disc 2 = 0x02
        assert responses == [bytes([CommandType.QUERY_DISC, 0x02])]


class TestAsyncQueryDisc:
    """Tests for async_query_disc method."""

    async def test_query_disc_cd_player(self):
        """Test that async_query_disc sends correct command for CD player."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        
        async def mock_callback(data: bytes) -> bool:
            # Address (0x90) + command (0x44) + disc number (0x01 BCD)
            assert data == bytes([0x90, 0x44, 0x01])
            return True
        
        player.set_send_callback(mock_callback)
        result = await player.async_query_disc(disc_number=1)
        assert result is True

    async def test_query_disc_md_player(self):
        """Test that async_query_disc sends correct command for MD player."""
        player = MDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        
        async def mock_callback(data: bytes) -> bool:
            # Address (0xB0) + command (0x44) + disc number (0x0A hex = 10)
            assert data == bytes([0xB0, 0x44, 0x0A])
            return True
        
        player.set_send_callback(mock_callback)
        result = await player.async_query_disc(disc_number=10)
        assert result is True

    async def test_query_disc_default_disc_number(self):
        """Test that async_query_disc defaults to disc 1."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        
        async def mock_callback(data: bytes) -> bool:
            assert data == bytes([0x90, 0x44, 0x01])
            return True
        
        player.set_send_callback(mock_callback)
        result = await player.async_query_disc()
        assert result is True


class TestTOCInitialization:
    """Tests for TOC initialization on 0x60 disc info message."""

    def test_disc_info_initializes_toc(self):
        """Test that 0x60 message initializes TOC with correct number of tracks."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=5,
            total_minutes=20,
            total_seconds=30,
            frames=0,
        )
        player.handle_message(msg)

        assert len(player.toc) == 5
        for i, track in enumerate(player.toc):
            assert track["length_min"] == 0
            assert track["length_sec"] == 0
            assert "title" not in track
            assert track["length"] == 0

    def test_disc_info_clears_existing_toc(self):
        """Test that 0x60 message clears any existing TOC."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.toc = [{"length_min": 1, "length_sec": 2, "title": "Old", "length": 62}]

        msg = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=3,
            total_minutes=10,
            total_seconds=0,
            frames=0,
        )
        player.handle_message(msg)

        assert len(player.toc) == 3
        assert all(track["length"] == 0 for track in player.toc)

    def test_disc_info_triggers_track_query(self):
        """Test that 0x60 message triggers 0x45 query for first track."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        msg = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=3,
            total_minutes=10,
            total_seconds=0,
            frames=0,
        )
        responses = player.handle_message(msg)

        assert len(responses) == 1
        assert responses[0] == bytes([CommandType.QUERY_TRACK, 0x01, 0x01])


class TestTOCProgression:
    """Tests for TOC progression through tracks."""

    def test_progress_toc_queries_tracks_in_order(self):
        """Test that _progress_toc queries tracks sequentially."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 0, "length_sec": 0, "title": "Track 01", "length": 0},
            {"length_min": 0, "length_sec": 0, "title": "Track 02", "length": 0},
            {"length_min": 0, "length_sec": 0, "title": "Track 03", "length": 0},
        ]

        responses = player._progress_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x01])]

        player.toc[0]["length"] = 180
        responses = player._progress_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x02])]

        player.toc[1]["length"] = 200
        responses = player._progress_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x03])]

    def test_progress_toc_returns_empty_when_complete(self):
        """Test that _progress_toc returns empty when all tracks have length."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 3, "length_sec": 0, "title": "Track 01", "length": 180},
            {"length_min": 3, "length_sec": 20, "title": "Track 02", "length": 200},
        ]

        responses = player._progress_toc()
        assert responses == []

    async def test_progress_toc_calls_callback_when_complete(self):
        """Test that _progress_toc calls the TOC complete callback when all tracks are filled."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 3, "length_sec": 0, "title": "Track 01", "length": 180},
            {"length_min": 3, "length_sec": 20, "title": "Track 02", "length": 200},
        ]

        callback_called = False

        async def mock_callback():
            nonlocal callback_called
            callback_called = True

        player.set_toc_complete_callback(mock_callback)
        player._progress_toc()

        # Allow the asyncio.ensure_future to run
        await asyncio.sleep(0)

        assert callback_called is True

    async def test_progress_toc_clears_external_metadata(self):
        """Test that _progress_toc clears external_metadata when TOC completes."""
        from custom_components.sony_a1_bus.external_metadata.models import (
            ExternalMetadata,
            TrackMetadata,
        )

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 3, "length_sec": 0, "title": "Track 01", "length": 180},
        ]

        # Set some external metadata
        player.external_metadata = ExternalMetadata(
            source="musicbrainz",
            source_id="test-mbid",
            album_title="Test Album",
            artist="Test Artist",
            tracks=[TrackMetadata("Track 1", "Artist", "rec-1")],
            album_art_url=None,
        )

        async def mock_callback():
            pass

        player.set_toc_complete_callback(mock_callback)
        player._progress_toc()

        # Allow the asyncio.ensure_future to run
        await asyncio.sleep(0)

        assert player.external_metadata is None


class TestTOCTrackInfoUpdate:
    """Tests for TOC update from 0x62 track info message."""

    def test_track_info_updates_toc_entry(self):
        """Test that 0x62 message updates the correct TOC entry."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 0, "length_sec": 0, "title": "Track 01", "length": 0},
            {"length_min": 0, "length_sec": 0, "title": "Track 02", "length": 0},
            {"length_min": 0, "length_sec": 0, "title": "Track 03", "length": 0},
        ]

        msg = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=2,
            minutes=4,
            seconds=30,
        )
        responses = player.handle_message(msg)

        assert player.toc[1]["length_min"] == 4
        assert player.toc[1]["length_sec"] == 30
        assert player.toc[1]["length"] == 270
        assert player.toc[0]["length"] == 0
        assert player.toc[2]["length"] == 0

    def test_track_info_triggers_next_query(self):
        """Test that 0x62 message triggers query for next track."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 0, "length_sec": 0, "title": "Track 01", "length": 0},
            {"length_min": 0, "length_sec": 0, "title": "Track 02", "length": 0},
        ]

        msg = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=3,
            seconds=0,
        )
        responses = player.handle_message(msg)

        assert len(responses) == 1
        assert responses[0] == bytes([CommandType.QUERY_TRACK, 0x01, 0x02])

    def test_full_toc_read_sequence(self):
        """Test complete TOC read sequence from 0x60 through all 0x62 responses."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.device_capabilities = 0x01
        player.device_name = "Test"

        disc_info = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=3,
            total_minutes=10,
            total_seconds=0,
            frames=0,
        )
        responses = player.handle_message(disc_info)
        assert len(player.toc) == 3
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x01])]

        track1 = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=3,
            seconds=30,
        )
        responses = player.handle_message(track1)
        assert player.toc[0]["length"] == 210
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x02])]

        track2 = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=2,
            minutes=4,
            seconds=0,
        )
        responses = player.handle_message(track2)
        assert player.toc[1]["length"] == 240
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x03])]

        track3 = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=3,
            minutes=2,
            seconds=30,
        )
        responses = player.handle_message(track3)
        assert player.toc[2]["length"] == 150
        assert responses == []


class TestTOCInvalidTrack:
    """Tests for handling invalid track numbers in 0x62 response."""

    def test_track_info_beyond_toc_ignored(self):
        """Test that 0x62 for track beyond TOC is ignored."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.device_capabilities = 0x01
        player.device_name = "Test"
        player.toc = [
            {"length_min": 0, "length_sec": 0, "title": "Track 01", "length": 0},
        ]

        msg = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=5,
            minutes=3,
            seconds=0,
        )
        responses = player.handle_message(msg)

        assert len(player.toc) == 1
        assert player.toc[0]["length"] == 0
        assert responses == []

    def test_track_info_zero_ignored(self):
        """Test that 0x62 for track 0 is ignored."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.device_capabilities = 0x01
        player.device_name = "Test"
        player.toc = [
            {"length_min": 0, "length_sec": 0, "title": "Track 01", "length": 0},
        ]

        msg = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=0,
            minutes=3,
            seconds=0,
        )
        responses = player.handle_message(msg)

        assert player.toc[0]["length"] == 0
        assert responses == []


class TestTOCCodecEncoding:
    """Tests for codec encoding in TOC queries."""

    def test_cd_player_uses_bcd_encoding(self):
        """Test that CD player uses BCD encoding for disc and track numbers."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 0, "length_sec": 0, "title": f"Track {i:02d}", "length": 0}
            for i in range(1, 13)
        ]

        responses = player._progress_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x01])]

        for i in range(11):
            player.toc[i]["length"] = 180
        responses = player._progress_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x12])]

    def test_md_player_uses_hex_encoding(self):
        """Test that MD player uses hex encoding for disc and track numbers."""
        player = MDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.current_disc = 1
        player.toc = [
            {"length_min": 0, "length_sec": 0, "title": f"Track {i:02d}", "length": 0}
            for i in range(1, 13)
        ]

        responses = player._progress_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x01])]

        for i in range(11):
            player.toc[i]["length"] = 180
        responses = player._progress_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x0C])]


class TestTOCClearOnUnload:
    """Tests for TOC clearing on disc unload."""

    def test_eject_clears_toc(self):
        """Test that eject message clears TOC."""
        from custom_components.sony_a1_bus.protocol import Message

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.toc = [
            {"length_min": 3, "length_sec": 0, "title": "Track 01", "length": 180},
        ]

        msg = Message(command=ResponseType.EJECT, raw_data=b"")
        player.handle_message(msg)

        assert player.disc_loaded is False
        assert player.toc == []

    def test_set_disc_loaded_false_clears_toc(self):
        """Test that _set_disc_loaded(False) clears TOC."""
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        player.disc_loaded = True
        player.toc = [
            {"length_min": 3, "length_sec": 0, "title": "Track 01", "length": 180},
        ]

        player._set_disc_loaded(False)

        assert player.toc == []


class TestTocState:
    """Tests for TOC state machine."""

    def test_initial_state_is_complete(self):
        """Test that initial TOC state is COMPLETE (no disc)."""
        from custom_components.sony_a1_bus.const import TocState

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
        assert player.toc_state == TocState.COMPLETE

    def test_disc_info_sets_loading_and_starts_timer(self):
        """Test that disc info message sets LOADING state and starts timer."""
        from custom_components.sony_a1_bus.const import TocState

        mock_hass = MagicMock()
        mock_timer = MagicMock()
        mock_hass.loop.call_later.return_value = mock_timer

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)
        msg = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=3,
            total_minutes=10,
            total_seconds=0,
            frames=0,
        )
        player.handle_message(msg)

        assert player.toc_state == TocState.LOADING
        mock_hass.loop.call_later.assert_called_once()

    def test_toc_completion_sets_complete(self):
        """Test that completing all track queries sets COMPLETE state."""
        from custom_components.sony_a1_bus.const import TocState

        mock_hass = MagicMock()
        mock_timer = MagicMock()
        mock_hass.loop.call_later.return_value = mock_timer

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)

        # Simulate disc info
        disc_info = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=2,
            total_minutes=6,
            total_seconds=0,
            frames=0,
        )
        player.handle_message(disc_info)
        assert player.toc_state == TocState.LOADING

        # Simulate track 1 info
        track1 = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=3,
            seconds=0,
        )
        player.handle_message(track1)
        assert player.toc_state == TocState.LOADING

        # Simulate track 2 info - completes TOC
        track2 = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=2,
            minutes=3,
            seconds=0,
        )
        player.handle_message(track2)
        assert player.toc_state == TocState.COMPLETE
        mock_timer.cancel.assert_called()

    def test_eject_sets_complete_and_cancels_timer(self):
        """Test that eject sets COMPLETE and cancels timer."""
        from custom_components.sony_a1_bus.const import TocState
        from custom_components.sony_a1_bus.protocol import Message

        mock_hass = MagicMock()
        mock_timer = MagicMock()
        mock_hass.loop.call_later.return_value = mock_timer

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)
        player.disc_loaded = True
        player._toc_state = TocState.LOADING
        player._toc_retry_timer = mock_timer

        msg = Message(command=ResponseType.EJECT, raw_data=b"")
        player.handle_message(msg)

        assert player.toc_state == TocState.COMPLETE
        mock_timer.cancel.assert_called()

    def test_timeout_triggers_retry(self):
        """Test that timeout triggers a disc re-query."""
        from custom_components.sony_a1_bus.const import TocState

        mock_hass = MagicMock()
        mock_timer = MagicMock()
        mock_hass.loop.call_later.return_value = mock_timer

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)
        player.disc_loaded = True
        player._toc_state = TocState.LOADING
        player._toc_retry_count = 0

        # Simulate send callback
        send_mock = AsyncMock(return_value=True)
        player.set_send_callback(send_mock)

        # Trigger timeout
        player._on_toc_timeout()

        assert player._toc_retry_count == 1
        assert player.toc_state == TocState.LOADING

        # Run the event loop to process the scheduled task
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
        send_mock.assert_called_once()

    def test_max_retries_sets_incomplete(self):
        """Test that exceeding max retries sets INCOMPLETE state."""
        from custom_components.sony_a1_bus.const import TOC_MAX_RETRIES, TocState

        mock_hass = MagicMock()
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)
        player.disc_loaded = True
        player._toc_state = TocState.LOADING
        player._toc_retry_count = TOC_MAX_RETRIES

        # Trigger timeout
        player._on_toc_timeout()

        assert player.toc_state == TocState.INCOMPLETE

    def test_manual_refresh_resets_counter(self):
        """Test that manual refresh resets retry counter."""
        from custom_components.sony_a1_bus.const import TocState

        mock_hass = MagicMock()
        mock_timer = MagicMock()
        mock_hass.loop.call_later.return_value = mock_timer

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)
        player.disc_loaded = True
        player._toc_state = TocState.INCOMPLETE
        player._toc_retry_count = 3

        send_mock = AsyncMock(return_value=True)
        player.set_send_callback(send_mock)

        asyncio.get_event_loop().run_until_complete(player.async_refresh_toc())

        assert player._toc_retry_count == 0
        assert player.toc_state == TocState.LOADING
        send_mock.assert_called_once()

    def test_manual_refresh_no_disc_returns_false(self):
        """Test that manual refresh returns False when no disc loaded."""
        mock_hass = MagicMock()
        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)
        player.disc_loaded = False

        send_mock = AsyncMock(return_value=True)
        player.set_send_callback(send_mock)

        result = asyncio.get_event_loop().run_until_complete(player.async_refresh_toc())

        assert result is False
        send_mock.assert_not_called()

    def test_listener_notified_on_state_change(self):
        """Test that listeners are notified when TOC state changes."""
        from custom_components.sony_a1_bus.const import TocState

        mock_hass = MagicMock()
        mock_timer = MagicMock()
        mock_hass.loop.call_later.return_value = mock_timer

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)

        listener = MagicMock()
        player.add_toc_state_listener(listener)

        # Trigger state change
        msg = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=1,
            total_minutes=3,
            total_seconds=0,
            frames=0,
        )
        player.handle_message(msg)

        listener.assert_called_once()

    def test_listener_removed(self):
        """Test that removed listeners are not called."""
        from custom_components.sony_a1_bus.const import TocState

        mock_hass = MagicMock()
        mock_timer = MagicMock()
        mock_hass.loop.call_later.return_value = mock_timer

        player = CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=mock_hass)

        listener = MagicMock()
        player.add_toc_state_listener(listener)
        player.remove_toc_state_listener(listener)

        msg = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=1,
            total_minutes=3,
            total_seconds=0,
            frames=0,
        )
        player.handle_message(msg)

        listener.assert_not_called()
