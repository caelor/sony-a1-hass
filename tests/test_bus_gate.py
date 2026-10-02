"""Tests for bus transmission gate."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from custom_components.sony_a1_bus.bus_gate import (
    BusTransmissionGate,
    MessagePriority,
)


class TestMessagePriority:
    """Tests for MessagePriority enum."""

    def test_normal_priority_value(self):
        """NORMAL priority should have value 0."""
        assert MessagePriority.NORMAL == 0

    def test_high_priority_value(self):
        """HIGH priority should have value 1."""
        assert MessagePriority.HIGH == 1


class TestBusTransmissionGate:
    """Tests for BusTransmissionGate."""

    async def test_gate_no_wait_on_first_message(self):
        """Gate should not wait if no RX has been recorded."""
        gate = BusTransmissionGate()
        
        start = time.monotonic()
        await gate.wait_for_silence(MessagePriority.NORMAL)
        elapsed = time.monotonic() - start
        
        # Should complete almost immediately
        assert elapsed < 0.01

    async def test_gate_waits_for_normal_silence(self):
        """Gate should wait for 200ms silence for NORMAL priority."""
        gate = BusTransmissionGate(normal_silence_sec=0.2)
        
        # Record an RX
        gate.record_rx()
        
        start = time.monotonic()
        await gate.wait_for_silence(MessagePriority.NORMAL)
        elapsed = time.monotonic() - start
        
        # Should wait approximately 200ms
        assert 0.19 <= elapsed <= 0.25

    async def test_gate_waits_for_high_silence(self):
        """Gate should wait for 50ms silence for HIGH priority."""
        gate = BusTransmissionGate(high_priority_silence_sec=0.05)
        
        # Record an RX
        gate.record_rx()
        
        start = time.monotonic()
        await gate.wait_for_silence(MessagePriority.HIGH)
        elapsed = time.monotonic() - start
        
        # Should wait approximately 50ms
        assert 0.04 <= elapsed <= 0.10

    async def test_gate_no_wait_after_silence(self):
        """Gate should not wait if bus has been silent long enough."""
        gate = BusTransmissionGate(normal_silence_sec=0.2)
        
        # Record an RX in the past (simulate old timestamp)
        gate._last_rx_time = time.monotonic() - 1.0  # 1 second ago
        
        start = time.monotonic()
        await gate.wait_for_silence(MessagePriority.NORMAL)
        elapsed = time.monotonic() - start
        
        # Should complete almost immediately
        assert elapsed < 0.01

    async def test_record_rx_updates_timestamp(self):
        """record_rx should update the last RX timestamp."""
        gate = BusTransmissionGate()
        
        assert gate._last_rx_time == 0.0
        
        gate.record_rx()
        assert gate._last_rx_time > 0.0
        
        old_time = gate._last_rx_time
        gate.record_rx()
        assert gate._last_rx_time >= old_time

    async def test_gate_concurrent_access(self):
        """Gate should handle concurrent access safely."""
        gate = BusTransmissionGate(normal_silence_sec=0.1)
        
        # Record an RX
        gate.record_rx()
        
        # Start multiple concurrent waits
        tasks = [
            gate.wait_for_silence(MessagePriority.NORMAL)
            for _ in range(5)
        ]
        
        start = time.monotonic()
        await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start
        
        # All should complete in approximately the same time (serialized by lock)
        # Total time should be approximately 100ms * 5 = 500ms if serialized
        # But since they all wait for the same condition, they should complete
        # within a reasonable time
        assert elapsed < 1.0

    async def test_gate_default_silence_values(self):
        """Gate should use default silence values if not specified."""
        gate = BusTransmissionGate()
        
        assert gate._normal_silence_sec == 0.2
        assert gate._high_priority_silence_sec == 0.05

    async def test_gate_custom_silence_values(self):
        """Gate should accept custom silence values."""
        gate = BusTransmissionGate(
            normal_silence_sec=0.5,
            high_priority_silence_sec=0.1,
        )
        
        assert gate._normal_silence_sec == 0.5
        assert gate._high_priority_silence_sec == 0.1


class TestBusTransmissionGateLogging:
    """Tests for bus gate logging."""

    async def test_gate_logs_wait_time(self, caplog):
        """Gate should log wait time at debug level."""
        gate = BusTransmissionGate(normal_silence_sec=0.1)
        gate.record_rx()
        
        with caplog.at_level("DEBUG"):
            await gate.wait_for_silence(MessagePriority.NORMAL)
        
        assert "Bus gate: waiting" in caplog.text
        assert "priority=NORMAL" in caplog.text

    async def test_gate_logs_high_priority(self, caplog):
        """Gate should log HIGH priority correctly."""
        gate = BusTransmissionGate(high_priority_silence_sec=0.05)
        gate.record_rx()
        
        with caplog.at_level("DEBUG"):
            await gate.wait_for_silence(MessagePriority.HIGH)
        
        assert "priority=HIGH" in caplog.text
