"""Tests for the TimeEstimator class."""

import pytest

from custom_components.sony_a1_bus.devices.time_estimator import TimeEstimator


class FakeClock:
    """A fake clock for testing."""

    def __init__(self, time: float = 0.0) -> None:
        self._time = time

    def __call__(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        self._time += seconds


class TestTimeEstimator:
    """Tests for TimeEstimator."""

    def test_initial_state_is_stopped(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        assert estimator.state == "stopped"
        assert estimator.is_stopped is True
        assert estimator.is_playing is False
        assert estimator.is_paused is False

    def test_initial_position_is_zero(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        assert estimator.get_position() == 0.0

    def test_play_transitions_to_playing(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        assert estimator.state == "playing"
        assert estimator.is_playing is True

    def test_play_while_playing_does_not_reset(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(5.0)
        estimator.play()  # Should not reset
        assert estimator.get_position() == 5.0

    def test_position_advances_while_playing(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        assert estimator.get_position() == 10.0

    def test_pause_transitions_to_paused(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(5.0)
        estimator.pause()
        assert estimator.state == "paused"
        assert estimator.is_paused is True

    def test_pause_accumulates_position(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.pause()
        assert estimator.get_position() == 10.0

    def test_position_frozen_while_paused(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.pause()
        clock.advance(5.0)
        assert estimator.get_position() == 10.0

    def test_resume_from_pause_continues_from_accumulated(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.pause()
        clock.advance(5.0)
        estimator.play()
        clock.advance(3.0)
        assert estimator.get_position() == 13.0

    def test_stop_transitions_to_stopped(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.stop()
        assert estimator.state == "stopped"
        assert estimator.is_stopped is True

    def test_stop_resets_position_to_zero(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.stop()
        assert estimator.get_position() == 0.0

    def test_position_frozen_while_stopped(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.stop()
        clock.advance(5.0)
        assert estimator.get_position() == 0.0

    def test_set_position_updates_immediately_when_stopped(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.set_position(42.0)
        assert estimator.get_position() == 42.0

    def test_set_position_updates_immediately_when_paused(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.pause()
        estimator.set_position(42.0)
        assert estimator.get_position() == 42.0

    def test_set_position_updates_immediately_when_playing(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.set_position(42.0)
        assert estimator.get_position() == 42.0
        clock.advance(5.0)
        assert estimator.get_position() == 47.0

    def test_set_position_to_zero(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.set_position(0.0)
        assert estimator.get_position() == 0.0

    def test_multiple_play_pause_cycles(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        # First cycle: play 10s, pause
        estimator.play()
        clock.advance(10.0)
        estimator.pause()
        # Second cycle: play 5s, pause
        estimator.play()
        clock.advance(5.0)
        estimator.pause()
        # Third cycle: play 3s
        estimator.play()
        clock.advance(3.0)
        assert estimator.get_position() == 18.0

    def test_play_from_paused_does_not_double_count(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.pause()
        estimator.play()
        clock.advance(5.0)
        assert estimator.get_position() == 15.0

    def test_stop_then_play_starts_from_zero(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.stop()
        estimator.play()
        clock.advance(5.0)
        assert estimator.get_position() == 5.0

    def test_pause_while_paused_is_noop(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.play()
        clock.advance(10.0)
        estimator.pause()
        clock.advance(5.0)
        estimator.pause()  # Should not change anything
        assert estimator.get_position() == 10.0

    def test_stop_while_stopped_is_noop(self):
        clock = FakeClock()
        estimator = TimeEstimator(clock=clock)
        estimator.stop()
        assert estimator.get_position() == 0.0
        assert estimator.state == "stopped"

    def test_default_clock_is_time_monotonic(self):
        estimator = TimeEstimator()
        # Should not raise
        estimator.play()
        position = estimator.get_position()
        assert position >= 0.0
