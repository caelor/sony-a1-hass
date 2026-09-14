"""Tests for external_metadata/fingerprint.py."""

from custom_components.sony_a1_bus.external_metadata.fingerprint import (
    build_toc_string,
    compute_fingerprint,
)


def _make_toc(lengths: list[int]) -> list[dict]:
    return [{"length_min": l // 60, "length_sec": l % 60, "title": f"Track {i+1:02d}", "length": l} for i, l in enumerate(lengths)]


class TestComputeFingerprint:
    def test_basic(self):
        toc = _make_toc([200, 180, 300])
        result = compute_fingerprint(toc, 680)
        assert result == "680:3:200,180,300"

    def test_single_track(self):
        toc = _make_toc([240])
        result = compute_fingerprint(toc, 240)
        assert result == "240:1:240"

    def test_empty_toc(self):
        result = compute_fingerprint([], 0)
        assert result == "0:0:"

    def test_deterministic(self):
        toc = _make_toc([200, 180])
        r1 = compute_fingerprint(toc, 380)
        r2 = compute_fingerprint(toc, 380)
        assert r1 == r2

    def test_different_lengths_different_fingerprint(self):
        toc1 = _make_toc([200, 180])
        toc2 = _make_toc([200, 181])
        assert compute_fingerprint(toc1, 380) != compute_fingerprint(toc2, 381)


class TestBuildTocString:
    def test_basic(self):
        toc = _make_toc([200, 180])
        result = build_toc_string(toc, 380)
        # Track 1: 150, Track 2: 150 + 200*75 = 15150, Leadout: 15150 + 180*75 = 28650
        assert result == "1 2 28650 150 15150"

    def test_single_track(self):
        toc = _make_toc([240])
        result = build_toc_string(toc, 240)
        # Track 1: 150, Leadout: 150 + 240*75 = 18150
        assert result == "1 1 18150 150"

    def test_three_tracks(self):
        toc = _make_toc([100, 200, 150])
        result = build_toc_string(toc, 450)
        # Track 1: 150
        # Track 2: 150 + 100*75 = 7650
        # Track 3: 7650 + 200*75 = 22650
        # Leadout: 22650 + 150*75 = 33900
        assert result == "1 3 33900 150 7650 22650"

    def test_empty_toc(self):
        result = build_toc_string([], 0)
        assert result == "1 0 150 "

    def test_leadout_derived_from_track_lengths(self):
        toc = _make_toc([200, 180])
        # total_seconds differs from sum of track lengths
        result = build_toc_string(toc, 400)
        # Leadout should be 150 + 200*75 + 180*75 = 28650, not 400*75 = 30000
        assert result == "1 2 28650 150 15150"
