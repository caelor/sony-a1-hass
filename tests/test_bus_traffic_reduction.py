"""Tests for bus traffic reduction features (Issues 1.1, 1.2, 1.3, 2.1, 2.2)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sony_a1_bus.bus_gate import MessagePriority
from custom_components.sony_a1_bus.const import (
    INTER_MESSAGE_DELAY_S,
    RETRY_COUNT_STATUS_QUERY,
    RETRY_COUNT_TOC_QUERY,
    CommandType,
    get_retry_count_for_command,
)
from custom_components.sony_a1_bus.devices.cd_player import CDPlayer


class TestGetRetryCountForCommand:
    """Tests for get_retry_count_for_command helper."""

    def test_query_disc_returns_toc_retry_count(self):
        """QUERY_DISC (0x44) should return RETRY_COUNT_TOC_QUERY."""
        cmd = bytes([CommandType.QUERY_DISC, 0x01])
        assert get_retry_count_for_command(cmd) == RETRY_COUNT_TOC_QUERY

    def test_query_track_returns_toc_retry_count(self):
        """QUERY_TRACK (0x45) should return RETRY_COUNT_TOC_QUERY."""
        cmd = bytes([CommandType.QUERY_TRACK, 0x01, 0x01])
        assert get_retry_count_for_command(cmd) == RETRY_COUNT_TOC_QUERY

    def test_query_disc_name_returns_toc_retry_count(self):
        """QUERY_DISC_NAME (0x58) should return RETRY_COUNT_TOC_QUERY."""
        cmd = bytes([CommandType.QUERY_DISC_NAME, 0x01, 0x00])
        assert get_retry_count_for_command(cmd) == RETRY_COUNT_TOC_QUERY

    def test_query_track_name_returns_toc_retry_count(self):
        """QUERY_TRACK_NAME (0x5A) should return RETRY_COUNT_TOC_QUERY."""
        cmd = bytes([CommandType.QUERY_TRACK_NAME, 0x01, 0x00])
        assert get_retry_count_for_command(cmd) == RETRY_COUNT_TOC_QUERY

    def test_query_status_returns_status_retry_count(self):
        """QUERY_STATUS (0x0F) should return RETRY_COUNT_STATUS_QUERY."""
        cmd = bytes([CommandType.QUERY_STATUS])
        assert get_retry_count_for_command(cmd) == RETRY_COUNT_STATUS_QUERY

    def test_play_returns_zero_retries(self):
        """CMD_PLAY (0x00) should return 0 retries (transport command)."""
        cmd = bytes([CommandType.CMD_PLAY])
        assert get_retry_count_for_command(cmd) == 0

    def test_stop_returns_zero_retries(self):
        """CMD_STOP (0x01) should return 0 retries (transport command)."""
        cmd = bytes([CommandType.CMD_STOP])
        assert get_retry_count_for_command(cmd) == 0

    def test_pause_returns_zero_retries(self):
        """CMD_PAUSE (0x02) should return 0 retries (transport command)."""
        cmd = bytes([CommandType.CMD_PAUSE])
        assert get_retry_count_for_command(cmd) == 0

    def test_empty_command_returns_zero(self):
        """Empty command should return 0 retries."""
        assert get_retry_count_for_command(b"") == 0


class TestAsyncSendCommandRetries:
    """Tests for retry count parameter in async_send_command."""

    async def test_query_status_passes_retry_count(self):
        """async_query_status should pass RETRY_COUNT_STATUS_QUERY to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_retries = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_retries
            captured_retries = max_retries
            return True

        player.set_send_callback(mock_callback)
        await player.async_query_status()

        assert captured_retries == RETRY_COUNT_STATUS_QUERY

    async def test_query_disc_passes_retry_count(self):
        """async_query_disc should pass RETRY_COUNT_TOC_QUERY to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_retries = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_retries
            captured_retries = max_retries
            return True

        player.set_send_callback(mock_callback)
        await player.async_query_disc()

        assert captured_retries == RETRY_COUNT_TOC_QUERY

    async def test_play_passes_zero_retries(self):
        """async_play should pass 0 retries to callback (transport command)."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_retries = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_retries
            captured_retries = max_retries
            return True

        player.set_send_callback(mock_callback)
        await player.async_play()

        assert captured_retries == 0


class TestInterMessageDelay:
    """Tests for inter-message delay in send loop."""

    def test_inter_message_delay_constant(self):
        """Verify INTER_MESSAGE_DELAY_S is set to 20ms."""
        from custom_components.sony_a1_bus.const import INTER_MESSAGE_DELAY_S

        assert INTER_MESSAGE_DELAY_S == 0.02


class TestMessagePriority:
    """Tests for message priority in async_send_command."""

    async def test_play_uses_high_priority(self):
        """async_play should pass HIGH priority to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_priority = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_priority
            captured_priority = priority
            return True

        player.set_send_callback(mock_callback)
        await player.async_play()

        assert captured_priority == MessagePriority.HIGH

    async def test_stop_uses_high_priority(self):
        """async_stop should pass HIGH priority to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_priority = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_priority
            captured_priority = priority
            return True

        player.set_send_callback(mock_callback)
        await player.async_stop()

        assert captured_priority == MessagePriority.HIGH

    async def test_pause_uses_high_priority(self):
        """async_pause should pass HIGH priority to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_priority = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_priority
            captured_priority = priority
            return True

        player.set_send_callback(mock_callback)
        await player.async_pause()

        assert captured_priority == MessagePriority.HIGH

    async def test_next_track_uses_high_priority(self):
        """async_next_track should pass HIGH priority to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_priority = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_priority
            captured_priority = priority
            return True

        player.set_send_callback(mock_callback)
        await player.async_next_track()

        assert captured_priority == MessagePriority.HIGH

    async def test_previous_track_uses_high_priority(self):
        """async_previous_track should pass HIGH priority to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_priority = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_priority
            captured_priority = priority
            return True

        player.set_send_callback(mock_callback)
        await player.async_previous_track()

        assert captured_priority == MessagePriority.HIGH

    async def test_query_status_uses_normal_priority(self):
        """async_query_status should pass NORMAL priority to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_priority = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_priority
            captured_priority = priority
            return True

        player.set_send_callback(mock_callback)
        await player.async_query_status()

        assert captured_priority == MessagePriority.NORMAL

    async def test_query_disc_uses_normal_priority(self):
        """async_query_disc should pass NORMAL priority to callback."""
        player = CDPlayer(
            sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock()
        )

        captured_priority = None

        async def mock_callback(data: bytes, max_retries: int, priority: MessagePriority) -> bool:
            nonlocal captured_priority
            captured_priority = priority
            return True

        player.set_send_callback(mock_callback)
        await player.async_query_disc()

        assert captured_priority == MessagePriority.NORMAL
