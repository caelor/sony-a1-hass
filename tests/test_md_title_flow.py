"""Tests for MDPlayer title reading flow."""

import asyncio
from unittest.mock import MagicMock

from custom_components.sony_a1_bus.const import (
    CommandType,
    ResponseType,
)
from custom_components.sony_a1_bus.devices.md_player import MDPlayer
from custom_components.sony_a1_bus.protocol import (
    DiscInfoMessage,
    DiscTextContinuationMessage,
    DiscTextFirstBlockMessage,
    Message,
    TrackInfoMessage,
    TrackTextContinuationMessage,
    TrackTextFirstBlockMessage,
)


def _make_md_player() -> MDPlayer:
    player = MDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())
    player.device_capabilities = 0x01
    player.device_name = "Test"
    return player


def _populate_lengths(player: MDPlayer, track_count: int = 3) -> None:
    """Simulate a full disc info + track info sequence to populate lengths."""
    disc_info = DiscInfoMessage(
        command=ResponseType.DISC_INFO,
        raw_data=b"",
        disc_number=1,
        indexes=1,
        track_count=track_count,
        total_minutes=10,
        total_seconds=0,
        frames=0,
    )
    player.handle_message(disc_info)

    for i in range(1, track_count + 1):
        track_info = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=i,
            minutes=3,
            seconds=0,
        )
        player.handle_message(track_info)


class TestMDProgressDeviceSpecificToc:
    """Tests for MDPlayer._progress_device_specific_toc."""

    def test_queries_disc_name_first(self):
        """Test that disc name is queried before track names."""
        player = _make_md_player()
        _populate_lengths(player)

        responses = player._progress_device_specific_toc()
        assert responses == [bytes([CommandType.QUERY_DISC_NAME, 0x01, 0x00])]

    def test_queries_track_name_after_disc_name(self):
        """Test that track names are queried after disc name is set."""
        player = _make_md_player()
        _populate_lengths(player)
        player.disc_title = "Test Album"

        responses = player._progress_device_specific_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]

    def test_queries_tracks_sequentially(self):
        """Test that tracks are queried in order."""
        player = _make_md_player()
        _populate_lengths(player)
        player.disc_title = "Test Album"

        responses = player._progress_device_specific_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]

        player.toc[0]["title"] = "Track 1 Title"
        responses = player._progress_device_specific_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x02, 0x00])]

        player.toc[1]["title"] = "Track 2 Title"
        responses = player._progress_device_specific_toc()
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x03, 0x00])]

    def test_returns_empty_when_all_titles_set(self):
        """Test that empty list is returned when all titles are set."""
        player = _make_md_player()
        _populate_lengths(player)
        player.disc_title = "Test Album"
        for i in range(3):
            player.toc[i]["title"] = f"Track {i+1}"

        responses = player._progress_device_specific_toc()
        assert responses == []


class TestMDDiscTextHandling:
    """Tests for MD disc text (0x58/0x59) handling."""

    def test_disc_text_first_block_incomplete(self):
        """Test disc text first block without null terminator."""
        player = _make_md_player()
        _populate_lengths(player)

        msg = DiscTextFirstBlockMessage(
            command=ResponseType.DISC_TEXT_FIRST,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"A" * 14,
        )
        responses = player.handle_message(msg)
        assert player.disc_title is None
        assert responses == []

    def test_disc_text_first_block_complete(self):
        """Test disc text first block with null terminator."""
        player = _make_md_player()
        _populate_lengths(player)

        msg = DiscTextFirstBlockMessage(
            command=ResponseType.DISC_TEXT_FIRST,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"Test Album\x00\x00\x00\x00",
        )
        responses = player.handle_message(msg)
        assert player.disc_title == "Test Album"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]

    def test_disc_text_with_continuation(self):
        """Test disc text spanning multiple blocks."""
        player = _make_md_player()
        _populate_lengths(player)

        msg1 = DiscTextFirstBlockMessage(
            command=ResponseType.DISC_TEXT_FIRST,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"A" * 14,
        )
        player.handle_message(msg1)
        assert player.disc_title is None

        msg2 = DiscTextContinuationMessage(
            command=ResponseType.DISC_TEXT_CONTINUATION,
            raw_data=b"",
            block_number=2,
            data=b"B" * 14 + b"\x00\x00",
        )
        responses = player.handle_message(msg2)
        assert player.disc_title == "A" * 14 + "B" * 14
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]


class TestMDTrackTextHandling:
    """Tests for MD track text (0x5A/0x5B) handling."""

    def test_track_text_first_block_complete(self):
        """Test track text first block with null terminator."""
        player = _make_md_player()
        _populate_lengths(player)
        player.disc_title = "Album"

        msg = TrackTextFirstBlockMessage(
            command=ResponseType.TRACK_TEXT_FIRST,
            raw_data=b"",
            track_number=1,
            title_fragment=b"Track One\x00\x00\x00\x00\x00",
        )
        responses = player.handle_message(msg)
        assert player.toc[0]["title"] == "Track One"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x02, 0x00])]

    def test_track_text_with_continuation(self):
        """Test track text spanning multiple blocks."""
        player = _make_md_player()
        _populate_lengths(player)
        player.disc_title = "Album"

        msg1 = TrackTextFirstBlockMessage(
            command=ResponseType.TRACK_TEXT_FIRST,
            raw_data=b"",
            track_number=2,
            title_fragment=b"A" * 14,
        )
        player.handle_message(msg1)
        assert "title" not in player.toc[1]

        msg2 = TrackTextContinuationMessage(
            command=ResponseType.TRACK_TEXT_CONTINUATION,
            raw_data=b"",
            block_number=2,
            data=b"End\x00" + b"\x00" * 12,
        )
        responses = player.handle_message(msg2)
        assert player.toc[1]["title"] == "A" * 14 + "End"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]


class TestMDNoNameResponses:
    """Tests for 0x16/0x17 no name responses."""

    def test_no_disc_name_sets_placeholder(self):
        """Test that 0x16 sets disc_title to 'No Name'."""
        player = _make_md_player()
        _populate_lengths(player)

        msg = Message(command=ResponseType.NO_DISC_NAME, raw_data=b"")
        responses = player.handle_message(msg)
        assert player.disc_title == "No Name"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]

    def test_no_track_name_sets_placeholder(self):
        """Test that 0x17 sets track title to 'No Name'."""
        player = _make_md_player()
        _populate_lengths(player)
        player.disc_title = "Album"

        msg = Message(command=ResponseType.NO_TRACK_NAME, raw_data=b"")
        responses = player.handle_message(msg)
        assert player.toc[0]["title"] == "No Name"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x02, 0x00])]


class TestMDFullTitleReadFlow:
    """Integration tests for the full MD title read flow."""

    async def test_full_flow_disc_and_track_titles(self):
        """Test complete flow from disc info through all title reads."""
        player = _make_md_player()

        async def mock_callback():
            pass

        player.set_toc_complete_callback(mock_callback)

        # 1. Disc info
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
        responses = player.handle_message(disc_info)
        assert responses == [bytes([CommandType.QUERY_TRACK, 0x01, 0x01])]

        # 2. Track lengths
        for i in range(1, 3):
            track_info = TrackInfoMessage(
                command=ResponseType.TRACK_INFO,
                raw_data=b"",
                disc_number=1,
                track_number=i,
                minutes=3,
                seconds=0,
            )
            responses = player.handle_message(track_info)

        # After last track info, _progress_device_specific_toc should query disc name
        assert responses == [bytes([CommandType.QUERY_DISC_NAME, 0x01, 0x00])]

        # 3. Disc title (complete in one block)
        disc_text = DiscTextFirstBlockMessage(
            command=ResponseType.DISC_TEXT_FIRST,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"My Album\x00\x00\x00\x00\x00\x00",
        )
        responses = player.handle_message(disc_text)
        assert player.disc_title == "My Album"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]

        # 4. Track 1 title
        track1_text = TrackTextFirstBlockMessage(
            command=ResponseType.TRACK_TEXT_FIRST,
            raw_data=b"",
            track_number=1,
            title_fragment=b"Song One\x00\x00\x00\x00\x00\x00",
        )
        responses = player.handle_message(track1_text)
        assert player.toc[0]["title"] == "Song One"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x02, 0x00])]

        # 5. Track 2 title
        track2_text = TrackTextFirstBlockMessage(
            command=ResponseType.TRACK_TEXT_FIRST,
            raw_data=b"",
            track_number=2,
            title_fragment=b"Song Two\x00\x00\x00\x00\x00\x00",
        )
        responses = player.handle_message(track2_text)
        assert player.toc[1]["title"] == "Song Two"
        assert responses == []

    async def test_full_flow_with_continuation_blocks(self):
        """Test flow with multi-block titles."""
        player = _make_md_player()

        callback_called = False

        async def mock_callback():
            nonlocal callback_called
            callback_called = True

        player.set_toc_complete_callback(mock_callback)

        # Populate lengths
        disc_info = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=1,
            total_minutes=3,
            total_seconds=0,
            frames=0,
        )
        player.handle_message(disc_info)
        track_info = TrackInfoMessage(
            command=ResponseType.TRACK_INFO,
            raw_data=b"",
            disc_number=1,
            track_number=1,
            minutes=3,
            seconds=0,
        )
        responses = player.handle_message(track_info)
        assert responses == [bytes([CommandType.QUERY_DISC_NAME, 0x01, 0x00])]

        # Disc title with continuation
        player.handle_message(DiscTextFirstBlockMessage(
            command=ResponseType.DISC_TEXT_FIRST,
            raw_data=b"",
            disc_number=1,
            title_fragment=b"A" * 14,
        ))
        assert player.disc_title is None

        responses = player.handle_message(DiscTextContinuationMessage(
            command=ResponseType.DISC_TEXT_CONTINUATION,
            raw_data=b"",
            block_number=2,
            data=b"Album\x00" + b"\x00" * 10,
        ))
        assert player.disc_title == "A" * 14 + "Album"
        assert responses == [bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])]

        # Track title with continuation
        player.handle_message(TrackTextFirstBlockMessage(
            command=ResponseType.TRACK_TEXT_FIRST,
            raw_data=b"",
            track_number=1,
            title_fragment=b"B" * 14,
        ))
        assert "title" not in player.toc[0]

        responses = player.handle_message(TrackTextContinuationMessage(
            command=ResponseType.TRACK_TEXT_CONTINUATION,
            raw_data=b"",
            block_number=2,
            data=b"Song\x00" + b"\x00" * 11,
        ))
        assert player.toc[0]["title"] == "B" * 14 + "Song"
        assert responses == []

        await asyncio.sleep(0)
        assert callback_called


class TestMDGetTrackTitle:
    """Tests for get_track_title accessor."""

    def test_returns_title_when_set(self):
        """Test that get_track_title returns set title."""
        player = _make_md_player()
        player.toc = [{"length": 180, "title": "My Song"}]
        assert player.get_track_title(0) == "My Song"

    def test_returns_default_when_no_title(self):
        """Test that get_track_title returns default when no title set."""
        player = _make_md_player()
        player.toc = [{"length": 180}]
        assert player.get_track_title(0) == "Track 01"

    def test_returns_default_for_out_of_range(self):
        """Test that get_track_title returns default for out-of-range index."""
        player = _make_md_player()
        player.toc = [{"length": 180}]
        assert player.get_track_title(5) == "Track 06"


class TestMDDiscTitleCleared:
    """Tests for disc_title clearing."""

    def test_disc_title_cleared_on_disc_info(self):
        """Test that disc_title is cleared when new disc info arrives."""
        player = _make_md_player()
        player.disc_title = "Old Album"

        disc_info = DiscInfoMessage(
            command=ResponseType.DISC_INFO,
            raw_data=b"",
            disc_number=1,
            indexes=1,
            track_count=1,
            total_minutes=3,
            total_seconds=0,
            frames=0,
        )
        player.handle_message(disc_info)
        assert player.disc_title is None

    def test_disc_title_cleared_on_eject(self):
        """Test that disc_title is cleared on eject."""
        player = _make_md_player()
        player.disc_loaded = True
        player.disc_title = "Old Album"

        msg = Message(command=ResponseType.EJECT, raw_data=b"")
        player.handle_message(msg)
        assert player.disc_title is None
