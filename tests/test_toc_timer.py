"""Tests for TOC timer reset behavior."""

import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant

from custom_components.sony_a1_bus.devices.md_player import MDPlayer
from custom_components.sony_a1_bus.const import TocState
from custom_components.sony_a1_bus.protocol import (
    DiscInfoMessage,
    TrackInfoMessage,
    DiscTextFirstBlockMessage,
    DiscTextContinuationMessage,
    TrackTextFirstBlockMessage,
    TrackTextContinuationMessage,
    TocReadCompleteMessage,
)


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
    yield player
    if player._toc_retry_timer is not None:
        player._cancel_toc_timer()


class TestTOCTimerReset:
    """Test that TOC timer is reset on progress."""

    def test_timer_reset_on_track_info(self, md_player):
        """Timer should reset when track info is received."""
        disc_info = DiscInfoMessage(
            command=0x60,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=22,
            total_minutes=79,
            total_seconds=26,
            frames=0,
        )
        md_player.handle_message(disc_info)
        
        assert md_player._toc_state == TocState.LOADING
        assert md_player._toc_retry_timer is not None
        initial_timer = md_player._toc_retry_timer
        
        track_info = TrackInfoMessage(
            command=0x62,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=2,
            seconds=59,
        )
        md_player.handle_message(track_info)
        
        assert md_player._toc_retry_timer is not None
        assert md_player._toc_retry_timer != initial_timer

    def test_timer_reset_on_disc_text_first(self, md_player):
        """Timer should reset when disc text first block is received."""
        disc_info = DiscInfoMessage(
            command=0x60,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=22,
            total_minutes=79,
            total_seconds=26,
            frames=0,
        )
        md_player.handle_message(disc_info)
        
        for i in range(1, 23):
            track_info = TrackInfoMessage(
                command=0x62,
                raw_data=b"",
                disc_number=1,
                track_number=i,
                minutes=3,
                seconds=35,
            )
            md_player.handle_message(track_info)
        
        initial_timer = md_player._toc_retry_timer
        
        disc_text = DiscTextFirstBlockMessage(
            command=0x58,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"Test Title\x00\x00\x00\x00",
        )
        md_player.handle_message(disc_text)
        
        assert md_player._toc_retry_timer is not None
        assert md_player._toc_retry_timer != initial_timer

    def test_timer_reset_on_disc_text_continuation(self, md_player):
        """Timer should reset when disc text continuation is received."""
        disc_info = DiscInfoMessage(
            command=0x60,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=22,
            total_minutes=79,
            total_seconds=26,
            frames=0,
        )
        md_player.handle_message(disc_info)
        
        for i in range(1, 23):
            track_info = TrackInfoMessage(
                command=0x62,
                raw_data=b"",
                disc_number=1,
                track_number=i,
                minutes=3,
                seconds=35,
            )
            md_player.handle_message(track_info)
        
        disc_text_first = DiscTextFirstBlockMessage(
            command=0x58,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"Test Title 123",
        )
        md_player.handle_message(disc_text_first)
        
        initial_timer = md_player._toc_retry_timer
        
        disc_text_cont = DiscTextContinuationMessage(
            command=0x59,
            raw_data=b"",
            block_number=2,
            data=b"Continuation\x00\x00\x00\x00",
        )
        md_player.handle_message(disc_text_cont)
        
        assert md_player._toc_retry_timer is not None
        assert md_player._toc_retry_timer != initial_timer

    def test_timer_reset_on_track_text_first(self, md_player):
        """Timer should reset when track text first block is received."""
        disc_info = DiscInfoMessage(
            command=0x60,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=22,
            total_minutes=79,
            total_seconds=26,
            frames=0,
        )
        md_player.handle_message(disc_info)
        
        for i in range(1, 23):
            track_info = TrackInfoMessage(
                command=0x62,
                raw_data=b"",
                disc_number=1,
                track_number=i,
                minutes=3,
                seconds=35,
            )
            md_player.handle_message(track_info)
        
        disc_text = DiscTextFirstBlockMessage(
            command=0x58,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"Disc Title" + b"\x00" * 6,
        )
        md_player.handle_message(disc_text)
        
        initial_timer = md_player._toc_retry_timer
        
        track_text = TrackTextFirstBlockMessage(
            command=0x5A,
            raw_data=b"",
            track_number=1,
            title_fragment=b"Track 1" + b"\x00" * 9,
        )
        md_player.handle_message(track_text)
        
        assert md_player._toc_retry_timer is not None
        assert md_player._toc_retry_timer != initial_timer

    def test_timer_reset_on_track_text_continuation(self, md_player):
        """Timer should reset when track text continuation is received."""
        disc_info = DiscInfoMessage(
            command=0x60,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=22,
            total_minutes=79,
            total_seconds=26,
            frames=0,
        )
        md_player.handle_message(disc_info)
        
        for i in range(1, 23):
            track_info = TrackInfoMessage(
                command=0x62,
                raw_data=b"",
                disc_number=1,
                track_number=i,
                minutes=3,
                seconds=35,
            )
            md_player.handle_message(track_info)
        
        disc_text = DiscTextFirstBlockMessage(
            command=0x58,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"Disc Title 123",
        )
        md_player.handle_message(disc_text)
        
        track_text_first = TrackTextFirstBlockMessage(
            command=0x5A,
            raw_data=b"",
            track_number=1,
            title_fragment=b"Track 1 Title 1",
        )
        md_player.handle_message(track_text_first)
        
        initial_timer = md_player._toc_retry_timer
        
        track_text_cont = TrackTextContinuationMessage(
            command=0x5B,
            raw_data=b"",
            block_number=2,
            data=b"Continuation\x00\x00\x00\x00",
        )
        md_player.handle_message(track_text_cont)
        
        assert md_player._toc_retry_timer is not None
        assert md_player._toc_retry_timer != initial_timer

    def test_timer_reset_on_no_disc_name(self, md_player):
        """Timer should reset when no disc name response is received."""
        disc_info = DiscInfoMessage(
            command=0x60,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=22,
            total_minutes=79,
            total_seconds=26,
            frames=0,
        )
        md_player.handle_message(disc_info)
        
        for i in range(1, 23):
            track_info = TrackInfoMessage(
                command=0x62,
                raw_data=b"",
                disc_number=1,
                track_number=i,
                minutes=3,
                seconds=35,
            )
            md_player.handle_message(track_info)
        
        initial_timer = md_player._toc_retry_timer
        
        no_disc_name = type('Message', (), {'command': 0x16, 'raw_data': b''})()
        md_player.handle_message(no_disc_name)
        
        assert md_player._toc_retry_timer is not None
        assert md_player._toc_retry_timer != initial_timer

    def test_timer_reset_on_no_track_name(self, md_player):
        """Timer should reset when no track name response is received."""
        disc_info = DiscInfoMessage(
            command=0x60,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=22,
            total_minutes=79,
            total_seconds=26,
            frames=0,
        )
        md_player.handle_message(disc_info)
        
        for i in range(1, 23):
            track_info = TrackInfoMessage(
                command=0x62,
                raw_data=b"",
                disc_number=1,
                track_number=i,
                minutes=3,
                seconds=35,
            )
            md_player.handle_message(track_info)
        
        disc_text = DiscTextFirstBlockMessage(
            command=0x58,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"Disc Title" + b"\x00" * 6,
        )
        md_player.handle_message(disc_text)
        
        initial_timer = md_player._toc_retry_timer
        
        no_track_name = type('Message', (), {'command': 0x17, 'raw_data': b''})()
        md_player.handle_message(no_track_name)
        
        assert md_player._toc_retry_timer is not None
        assert md_player._toc_retry_timer != initial_timer

    def test_timer_not_reset_when_not_loading(self, md_player):
        """Timer should not be reset when TOC state is not LOADING."""
        md_player._set_toc_state(TocState.COMPLETE)
        
        track_info = TrackInfoMessage(
            command=0x62,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=2,
            seconds=59,
        )
        md_player.handle_message(track_info)
        
        assert md_player._toc_retry_timer is None


class TestTOCReadComplete:
    """Test 0x71 TOC read complete handling."""

    def test_toc_read_complete_sets_disc_loaded(self, md_player):
        """0x71 should set disc_loaded if not already set."""
        md_player.disc_loaded = False
        
        toc_complete = TocReadCompleteMessage(
            command=0x71,
            raw_data=b"",
        )
        responses = md_player.handle_message(toc_complete)
        
        assert md_player.disc_loaded is True
        assert len(responses) > 0
        assert responses[0][0] == 0x44

    def test_toc_read_complete_refreshes_if_incomplete(self, md_player):
        """0x71 should refresh TOC if state is INCOMPLETE."""
        md_player.disc_loaded = True
        md_player._set_toc_state(TocState.INCOMPLETE)
        
        toc_complete = TocReadCompleteMessage(
            command=0x71,
            raw_data=b"",
        )
        responses = md_player.handle_message(toc_complete)
        
        assert len(responses) > 0
        assert responses[0][0] == 0x44

    def test_toc_read_complete_no_action_if_loading(self, md_player):
        """0x71 should not trigger refresh if already LOADING."""
        md_player.disc_loaded = True
        md_player._set_toc_state(TocState.LOADING)
        md_player.device_capabilities = 0xFF
        md_player.device_name = "Test MD"
        
        toc_complete = TocReadCompleteMessage(
            command=0x71,
            raw_data=b"",
        )
        responses = md_player.handle_message(toc_complete)
        
        assert len(responses) == 0

    def test_toc_read_complete_no_action_if_complete(self, md_player):
        """0x71 should not trigger refresh if already COMPLETE."""
        md_player.disc_loaded = True
        md_player._set_toc_state(TocState.COMPLETE)
        md_player.device_capabilities = 0xFF
        md_player.device_name = "Test MD"
        
        toc_complete = TocReadCompleteMessage(
            command=0x71,
            raw_data=b"",
        )
        responses = md_player.handle_message(toc_complete)
        
        assert len(responses) == 0
