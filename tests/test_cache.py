"""Tests for external_metadata/cache.py."""

import pytest

from custom_components.sony_a1_bus.external_metadata.cache import MetadataCache


@pytest.fixture
def cache(hass):
    return MetadataCache(hass)


class TestMetadataCache:
    async def test_initial_state(self, cache):
        await cache.async_load()
        assert cache.get_source_id("test_fp") is None
        assert cache.get_enabled("player1") is True  # defaults to True

    async def test_set_and_get_source_id(self, cache):
        await cache.async_load()
        cache.set_source_id("fp1", "musicbrainz:abc-123")
        assert cache.get_source_id("fp1") == "musicbrainz:abc-123"

    async def test_set_and_get_enabled(self, cache):
        await cache.async_load()
        assert cache.get_enabled("player1") is True
        cache.set_enabled("player1", False)
        assert cache.get_enabled("player1") is False

    async def test_persistence(self, hass):
        cache1 = MetadataCache(hass)
        await cache1.async_load()
        cache1.set_source_id("fp1", "musicbrainz:abc-123")
        cache1.set_enabled("player1", False)
        await cache1.async_save()

        cache2 = MetadataCache(hass)
        await cache2.async_load()
        assert cache2.get_source_id("fp1") == "musicbrainz:abc-123"
        assert cache2.get_enabled("player1") is False

    async def test_overwrite_source_id(self, cache):
        await cache.async_load()
        cache.set_source_id("fp1", "musicbrainz:old")
        cache.set_source_id("fp1", "musicbrainz:new")
        assert cache.get_source_id("fp1") == "musicbrainz:new"
