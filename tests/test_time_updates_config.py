"""Tests for switchable time updates configuration."""

import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.sony_a1_bus.devices.md_player import MDPlayer
from custom_components.sony_a1_bus.const import (
    CONF_ENABLE_TIME_UPDATES,
    DEFAULT_ENABLE_TIME_UPDATES,
)
from custom_components.sony_a1_bus.protocol import TrackChangeMessage


@pytest.fixture
def md_player(hass):
    """Create an MD player for testing."""
    player = MDPlayer(
        sub_index=0,
        bridge_node="test_bridge",
        bridge_device_id="test_device",
        hass=hass,
    )
    player.disc_loaded = True
    return player


class TestTimeUpdatesConfiguration:
    """Test switchable time updates."""

    def test_time_updates_disabled_by_default(self, md_player):
        """Time updates should be disabled by default."""
        assert md_player.enable_time_updates is False

    def test_disable_time_updates(self, md_player):
        """Time updates can be disabled."""
        md_player.set_time_updates_enabled(False)
        assert md_player.enable_time_updates is False

    def test_enable_time_updates(self, md_player):
        """Time updates can be re-enabled."""
        md_player.set_time_updates_enabled(False)
        md_player.set_time_updates_enabled(True)
        assert md_player.enable_time_updates is True

    def test_track_change_respects_time_updates_enabled(self, md_player):
        """Track change should request time updates when enabled."""
        md_player.enable_time_updates = True
        md_player.device_capabilities = 0xFF
        md_player.device_name = "Test MD"
        
        track_change = TrackChangeMessage(
            command=0x50,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=3,
            seconds=45,
        )
        responses = md_player.handle_message(track_change)
        
        # Should include CMD_SEND_TIME_UPDATES (0x25)
        assert any(r[0] == 0x25 for r in responses)

    def test_track_change_respects_time_updates_disabled(self, md_player):
        """Track change should not request time updates when disabled."""
        md_player.enable_time_updates = False
        md_player.device_capabilities = 0xFF
        md_player.device_name = "Test MD"
        
        track_change = TrackChangeMessage(
            command=0x50,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=3,
            seconds=45,
        )
        responses = md_player.handle_message(track_change)
        
        # Should NOT include CMD_SEND_TIME_UPDATES (0x25)
        assert not any(r[0] == 0x25 for r in responses)

    def test_track_change_still_queries_status_when_not_playing(self, md_player):
        """Track change should still query status when not playing, even with time updates disabled."""
        from custom_components.sony_a1_bus.const import TransportState
        md_player.enable_time_updates = False
        md_player.transport_state = TransportState.STOPPED
        md_player.device_capabilities = 0xFF
        md_player.device_name = "Test MD"
        
        track_change = TrackChangeMessage(
            command=0x50,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=3,
            seconds=45,
        )
        responses = md_player.handle_message(track_change)
        
        # Should include QUERY_STATUS (0x0F) but not CMD_SEND_TIME_UPDATES (0x25)
        assert any(r[0] == 0x0F for r in responses)
        assert not any(r[0] == 0x25 for r in responses)


class TestConfigFlow:
    """Test config flow options."""

    def test_default_options(self, hass):
        """Default options should include enable_time_updates."""
        from custom_components.sony_a1_bus.config_flow import SonyA1BusConfigFlow
        
        # The config flow should set default options
        assert DEFAULT_ENABLE_TIME_UPDATES is False

    def test_options_flow_handler_exists(self, hass):
        """Options flow handler should exist."""
        from custom_components.sony_a1_bus.config_flow import SonyA1BusOptionsFlowHandler
        
        # Should be able to import the options flow handler
        assert SonyA1BusOptionsFlowHandler is not None
