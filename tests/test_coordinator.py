"""Tests for coordinator.py."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.sony_a1_bus.coordinator import MetadataCoordinator
from custom_components.sony_a1_bus.external_metadata.models import (
    ExternalMetadata,
    TrackMetadata,
)


def _make_player(toc_lengths: list[int] | None = None):
    player = MagicMock()
    player.name = "Test Player"
    player.unique_id = "test_player_1"
    player.toc = []
    player.total_minutes = 0
    player.total_seconds = 0
    player.external_metadata = None
    player._notify_entities = MagicMock()

    if toc_lengths is not None:
        player.toc = [
            {"length_min": l // 60, "length_sec": l % 60, "title": f"Track {i+1:02d}", "length": l}
            for i, l in enumerate(toc_lengths)
        ]
        total = sum(toc_lengths)
        player.total_minutes = total // 60
        player.total_seconds = total % 60

    return player


@pytest.fixture
def coordinator(hass, mock_config_entry):
    coord = MetadataCoordinator(hass, mock_config_entry)
    return coord


class TestMetadataCoordinator:
    async def test_setup_loads_cache(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()
        assert coord.cache is not None

    async def test_on_toc_complete_disabled(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player([200, 180])
        coord.set_enabled(player, False)

        await coord.async_on_toc_complete(player)
        assert player.external_metadata is None

    async def test_on_toc_complete_with_cache_hit(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player([200, 180])
        fingerprint = f"{380}:2:200,180"

        coord.cache.set_source_id(fingerprint, "musicbrainz:test-mbid")

        mock_metadata = ExternalMetadata(
            source="musicbrainz",
            source_id="test-mbid",
            album_title="Test Album",
            artist="Test Artist",
            tracks=[TrackMetadata("Track 1", "Artist", "rec-1")],
            album_art_url=None,
        )

        with patch.object(coord._providers["musicbrainz"], "async_lookup_by_id", return_value=mock_metadata):
            await coord.async_on_toc_complete(player)

        assert player.external_metadata is not None
        assert player.external_metadata.album_title == "Test Album"

    async def test_on_toc_complete_with_cache_miss(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player([200, 180])

        mock_metadata = ExternalMetadata(
            source="musicbrainz",
            source_id="found-mbid",
            album_title="Found Album",
            artist="Found Artist",
            tracks=[],
            album_art_url=None,
        )

        with patch.object(coord._providers["musicbrainz"], "async_lookup", return_value="found-mbid"), \
             patch.object(coord._providers["musicbrainz"], "async_lookup_by_id", return_value=mock_metadata):
            await coord.async_on_toc_complete(player)

        assert player.external_metadata is not None
        assert player.external_metadata.album_title == "Found Album"
        assert coord.cache.get_source_id(f"{380}:2:200,180") == "musicbrainz:found-mbid"

    async def test_on_toc_complete_no_results(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player([200, 180])

        with patch.object(coord._providers["musicbrainz"], "async_lookup", return_value=None):
            await coord.async_on_toc_complete(player)

        assert player.external_metadata is None

    async def test_set_musicbrainz_id(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player([200, 180])

        mock_metadata = ExternalMetadata(
            source="musicbrainz",
            source_id="override-mbid",
            album_title="Override Album",
            artist="Override Artist",
            tracks=[],
            album_art_url=None,
        )

        with patch.object(coord._providers["musicbrainz"], "async_lookup_by_id", return_value=mock_metadata):
            await coord.async_set_musicbrainz_id(player, "override-mbid")

        assert player.external_metadata is not None
        assert player.external_metadata.source_id == "override-mbid"
        assert coord.cache.get_source_id(f"{380}:2:200,180") == "musicbrainz:override-mbid"

    async def test_set_musicbrainz_id_no_toc(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player()
        player.toc = []

        await coord.async_set_musicbrainz_id(player, "some-mbid")
        assert coord.cache.get_source_id("") is None

    async def test_is_enabled_default(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player()
        assert coord.is_enabled(player) is True

    async def test_set_enabled(self, hass, mock_config_entry):
        coord = MetadataCoordinator(hass, mock_config_entry)
        await coord.async_setup()

        player = _make_player()
        coord.set_enabled(player, False)
        assert coord.is_enabled(player) is False
