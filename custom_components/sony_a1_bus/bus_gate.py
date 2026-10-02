"""Bus transmission gate for collision avoidance."""

import asyncio
import logging
import time
from enum import IntEnum

_LOGGER = logging.getLogger(__name__)


class MessagePriority(IntEnum):
    """Message priority levels for bus transmission.
    
    NORMAL: Wait for full bus silence (200ms) before transmitting.
            Used for background tasks like TOC queries, status queries.
    HIGH:   Wait for reduced silence (50ms) before transmitting.
            Used for user-initiated commands like play/stop/pause.
    """
    NORMAL = 0
    HIGH = 1


class BusTransmissionGate:
    """Gate that enforces bus silence before transmitting.
    
    Tracks the last RX timestamp and provides a method to wait for
    a configurable silence period before allowing transmission.
    This prevents collisions during chatty periods on the bus.
    """
    
    def __init__(
        self,
        normal_silence_sec: float = 0.2,
        high_priority_silence_sec: float = 0.05,
    ) -> None:
        """Initialize the transmission gate.
        
        Args:
            normal_silence_sec: Silence threshold for NORMAL priority messages
            high_priority_silence_sec: Silence threshold for HIGH priority messages
        """
        self._last_rx_time: float = 0.0
        self._normal_silence_sec = normal_silence_sec
        self._high_priority_silence_sec = high_priority_silence_sec
        self._lock = asyncio.Lock()
    
    def record_rx(self) -> None:
        """Record that a message was received on the bus."""
        self._last_rx_time = time.monotonic()
    
    async def wait_for_silence(
        self,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        """Wait for bus silence before transmitting.
        
        Args:
            priority: Message priority level (NORMAL or HIGH)
        """
        async with self._lock:
            silence_threshold = (
                self._high_priority_silence_sec
                if priority == MessagePriority.HIGH
                else self._normal_silence_sec
            )
            
            elapsed = time.monotonic() - self._last_rx_time
            if elapsed < silence_threshold:
                wait_time = silence_threshold - elapsed
                _LOGGER.debug(
                    "Bus gate: waiting %.0fms for silence (priority=%s)",
                    wait_time * 1000,
                    priority.name,
                )
                await asyncio.sleep(wait_time)
