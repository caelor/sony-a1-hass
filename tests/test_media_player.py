"""Tests for media_player platform."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import DOMAIN
from custom_components.sony_a1_bus.devices.cd_player import CDPlayer
from custom_components.sony_a1_bus.external_metadata.models import (
    ExternalMetadata,
    TrackMetadata,
)
from custom_components.sony_a1_bus.media_player import SonyA1BusMediaPlayer


@pytest.fixture
def player():
    """Create a CD player for testing."""
    return CDPlayer(sub_index=0, bridge_node="test", bridge_device_id="dev1", hass=MagicMock())


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sony A1 Bus",
        data={},
        entry_id="test_entry_id",
    )


@pytest.fixture
def media_player(hass: HomeAssistant, player, mock_entry):
    """Create a media player entity for testing."""
    with patch("custom_components.sony_a1_bus.media_player.dr") as mock_dr:
        mock_dr.async_get.return_value.async_get_device.return_value = None
        return SonyA1BusMediaPlayer(hass, player, mock_entry)


def _make_external_metadata(
    album_title: str = "Test Album",
    artist: str = "Test Artist",
    tracks: list[TrackMetadata] | None = None,
    album_art_url: str | None = "https://example.com/art.jpg",
) -> ExternalMetadata:
    """Create ExternalMetadata for testing."""
    if tracks is None:
        tracks = [
            TrackMetadata(title="Track One", artist="Track Artist 1", recording_id="rec-1"),
            TrackMetadata(title="Track Two", artist="Track Artist 2", recording_id="rec-2"),
        ]
    return ExternalMetadata(
        source="musicbrainz",
        source_id="test-mbid",
        album_title=album_title,
        artist=artist,
        tracks=tracks,
        album_art_url=album_art_url,
    )


class TestMediaAttributesWithExternalMetadata:
    """Tests for media attributes when external_metadata is present."""

    def test_media_title_from_external_metadata(self, media_player, player):
        player.current_track = 1
        player.external_metadata = _make_external_metadata()
        assert media_player.media_title == "Track One"

    def test_media_title_from_external_metadata_track_2(self, media_player, player):
        player.current_track = 2
        player.external_metadata = _make_external_metadata()
        assert media_player.media_title == "Track Two"

    def test_media_artist_from_external_metadata_per_track(self, media_player, player):
        player.current_track = 1
        player.external_metadata = _make_external_metadata()
        assert media_player.media_artist == "Track Artist 1"

    def test_media_artist_falls_back_to_album_artist(self, media_player, player):
        player.current_track = 99
        player.external_metadata = _make_external_metadata()
        assert media_player.media_artist == "Test Artist"

    def test_media_album_name_from_external_metadata(self, media_player, player):
        player.current_track = 1
        player.external_metadata = _make_external_metadata()
        assert media_player.media_album_name == "Test Album"

    def test_media_album_artist_from_external_metadata(self, media_player, player):
        player.current_track = 1
        player.external_metadata = _make_external_metadata(artist="Album Artist")
        assert media_player.media_album_artist == "Album Artist"

    def test_media_image_url_from_external_metadata(self, media_player, player):
        player.current_track = 1
        player.external_metadata = _make_external_metadata(album_art_url="https://example.com/cover.jpg")
        assert media_player.media_image_url == "https://example.com/cover.jpg"

    def test_entity_picture_matches_media_image_url(self, media_player, player):
        player.current_track = 1
        player.external_metadata = _make_external_metadata(album_art_url="https://example.com/cover.jpg")
        assert media_player.entity_picture == media_player.media_image_url


class TestMediaAttributesWithTocFallback:
    """Tests for media attributes when external_metadata is None but toc is available."""

    def test_media_title_from_toc(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.toc = [
            {"length_min": 3, "length_sec": 0, "title": "TOC Track 1", "length": 180},
        ]
        player.external_metadata = None
        assert media_player.media_title == "TOC Track 1"

    def test_media_artist_default_when_no_external_metadata(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.toc = [{"length_min": 3, "length_sec": 0, "title": "Track", "length": 180}]
        player.external_metadata = None
        assert media_player.media_artist == "Unknown Artist"

    def test_media_album_name_default_when_no_external_metadata(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.toc = [{"length_min": 3, "length_sec": 0, "title": "Track", "length": 180}]
        player.external_metadata = None
        assert media_player.media_album_name == "Unknown Album"

    def test_media_album_artist_default_when_no_external_metadata(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.toc = [{"length_min": 3, "length_sec": 0, "title": "Track", "length": 180}]
        player.external_metadata = None
        assert media_player.media_album_artist == "Unknown Artist"

    def test_media_image_url_none_when_no_external_metadata(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.toc = [{"length_min": 3, "length_sec": 0, "title": "Track", "length": 180}]
        player.external_metadata = None
        assert media_player.media_image_url is None


class TestMediaAttributesDefaults:
    """Tests for media attributes when no metadata sources are available."""

    def test_media_title_default_format(self, media_player, player):
        player.current_track = 5
        player.disc_loaded = True
        player.toc = []
        player.external_metadata = None
        assert media_player.media_title == "Track 05"

    def test_media_title_default_track_12(self, media_player, player):
        player.current_track = 12
        player.disc_loaded = True
        player.toc = []
        player.external_metadata = None
        assert media_player.media_title == "Track 12"

    def test_media_artist_default(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.external_metadata = None
        assert media_player.media_artist == "Unknown Artist"

    def test_media_album_name_default(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.external_metadata = None
        assert media_player.media_album_name == "Unknown Album"

    def test_media_album_artist_default(self, media_player, player):
        player.current_track = 1
        player.disc_loaded = True
        player.external_metadata = None
        assert media_player.media_album_artist == "Unknown Artist"


class TestMediaAttributesNoTrack:
    """Tests for media attributes when current_track is 0 or invalid."""

    def test_media_title_none_when_no_track(self, media_player, player):
        player.current_track = 0
        assert media_player.media_title is None

    def test_media_artist_none_when_no_track(self, media_player, player):
        player.current_track = 0
        assert media_player.media_artist is None

    def test_media_album_name_none_when_no_track(self, media_player, player):
        player.current_track = 0
        assert media_player.media_album_name is None

    def test_media_album_artist_none_when_no_track(self, media_player, player):
        player.current_track = 0
        assert media_player.media_album_artist is None

    def test_media_image_url_none_when_no_track(self, media_player, player):
        player.current_track = 0
        player.external_metadata = _make_external_metadata()
        assert media_player.media_image_url == "https://example.com/art.jpg"

    def test_media_track_none_when_no_track(self, media_player, player):
        player.current_track = 0
        assert media_player.media_track is None


class TestMediaTrack:
    """Tests for media_track attribute."""

    def test_media_track_returns_current_track(self, media_player, player):
        player.current_track = 5
        player.disc_loaded = True
        assert media_player.media_track == 5

    def test_media_track_none_when_disc_not_loaded(self, media_player, player):
        player.current_track = 5
        player.disc_loaded = False
        assert media_player.media_track is None


class TestTrackIndex:
    """Tests for _track_index helper."""

    def test_track_index_returns_zero_based(self, media_player, player):
        player.current_track = 1
        assert media_player._track_index() == 0

    def test_track_index_returns_correct_index(self, media_player, player):
        player.current_track = 5
        assert media_player._track_index() == 4

    def test_track_index_none_when_zero(self, media_player, player):
        player.current_track = 0
        assert media_player._track_index() is None

    def test_track_index_none_when_negative(self, media_player, player):
        player.current_track = -1
        assert media_player._track_index() is None
