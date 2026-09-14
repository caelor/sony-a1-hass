"""Time position estimator for media playback.

Tracks play/pause/stop state and estimates current position based on elapsed time.
Used for devices that don't actively report playback position.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime


class TimeEstimator:
    """Estimates playback position based on state transitions and elapsed time.
    
    Tracks internal state (playing/paused/stopped) and accumulates position.
    When playing, position advances based on elapsed time. When paused/stopped,
    position remains fixed.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        """Initialize the time estimator.
        
        Args:
            clock: Callable returning current time in seconds. Defaults to time.monotonic.
        """
        self._clock = clock if clock is not None else time.monotonic
        self._state: str = "stopped"  # 'stopped', 'playing', 'paused'
        self._progress: float = 0.0  # Accumulated position in seconds
        self._playback_started: float | None = None  # Timestamp when playback started
        self.last_update_time: datetime | None = None

    def play(self) -> None:
        """Transition to playing state.
        
        If not already playing, records the current time as playback start.
        """
        if self._state != "playing":
            self._playback_started = self._clock()
            self._state = "playing"
            self.last_update_time = datetime.now()

    def pause(self) -> None:
        """Transition to paused state.
        
        If currently playing, accumulates elapsed time into progress.
        """
        if self._state == "playing":
            elapsed = self._clock() - self._playback_started
            self._progress += elapsed
            self._playback_started = None
            self._state = "paused"
            self.last_update_time = datetime.now()

    def stop(self) -> None:
        """Transition to stopped state.
        
        Resets progress to 0.
        """
        self._progress = 0.0
        self._playback_started = None
        self._state = "stopped"
        self.last_update_time = datetime.now()

    def set_position(self, position: float) -> None:
        """Set the current position to an arbitrary value.
        
        Updates immediately. If playing, resets the playback start timestamp
        so that get_position() returns the new value right away.
        
        Args:
            position: New position in seconds
        """
        self._progress = position
        if self._state == "playing":
            # Reset playback start so position updates immediately
            self._playback_started = self._clock()
        self.last_update_time = datetime.now()

    def get_position(self) -> float:
        """Get the current estimated position.
        
        If playing, returns accumulated progress plus elapsed time.
        If paused/stopped, returns accumulated progress.
        
        Returns:
            Current position in seconds
        """
        if self._state == "playing" and self._playback_started is not None:
            elapsed = self._clock() - self._playback_started
            self.last_update_time = datetime.now()
            return self._progress + elapsed
        return self._progress

    @property
    def state(self) -> str:
        """Get the current state.
        
        Returns:
            'stopped', 'playing', or 'paused'
        """
        return self._state

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._state == "playing"

    @property
    def is_paused(self) -> bool:
        """Check if currently paused."""
        return self._state == "paused"

    @property
    def is_stopped(self) -> bool:
        """Check if currently stopped."""
        return self._state == "stopped"
