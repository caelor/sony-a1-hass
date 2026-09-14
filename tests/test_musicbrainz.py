"""Tests for external_metadata/musicbrainz.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sony_a1_bus.external_metadata.musicbrainz import (
    SOURCE_NAME,
    MusicBrainzProvider,
    _calculate_offset_distance,
)


def _make_toc(lengths: list[int]) -> list[dict]:
    return [{"length_min": l // 60, "length_sec": l % 60, "title": f"Track {i+1:02d}", "length": l} for i, l in enumerate(lengths)]


@pytest.fixture
def provider(hass):
    return MusicBrainzProvider(hass)


class TestMusicBrainzProvider:
    async def test_lookup_returns_mbid(self, hass):
        provider = MusicBrainzProvider(hass)
        toc = _make_toc([200, 180])

        mock_result = {
            "release-list": [
                {"id": "test-mbid-123", "title": "Test Album"},
            ]
        }

        with patch("musicbrainzngs.get_releases_by_discid", return_value=mock_result):
            result = await provider.async_lookup("fp", toc, 380)

        assert result == "test-mbid-123"

    async def test_lookup_no_results(self, hass):
        provider = MusicBrainzProvider(hass)
        toc = _make_toc([200, 180])

        mock_result = {"release-list": []}

        with patch("musicbrainzngs.get_releases_by_discid", return_value=mock_result):
            result = await provider.async_lookup("fp", toc, 380)

        assert result is None

    async def test_lookup_response_error(self, hass):
        import musicbrainzngs
        provider = MusicBrainzProvider(hass)
        toc = _make_toc([200, 180])

        with patch("musicbrainzngs.get_releases_by_discid", side_effect=musicbrainzngs.ResponseError(cause=Exception("not found"))):
            result = await provider.async_lookup("fp", toc, 380)

        assert result is None

    async def test_lookup_by_id(self, hass):
        provider = MusicBrainzProvider(hass)

        mock_result = {
            "release": {
                "id": "test-mbid-123",
                "title": "Test Album",
                "artist-credit": [
                    {"artist": {"name": "Test Artist"}, "joinphrase": ""}
                ],
                "medium-list": [
                    {
                        "track-list": [
                            {
                                "title": "Track 1",
                                "recording": {"id": "rec-1", "title": "Track 1", "artist-credit": []},
                                "artist-credit": [],
                            },
                        ]
                    }
                ],
            }
        }

        mock_resp = AsyncMock()
        mock_resp.status = 302
        mock_resp.headers = {"Location": "https://example.com/image.jpg"}
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("musicbrainzngs.get_release_by_id", return_value=mock_result), \
             patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.async_lookup_by_id("test-mbid-123")

        assert result is not None
        assert result.source == SOURCE_NAME
        assert result.source_id == "test-mbid-123"
        assert result.album_title == "Test Album"
        assert result.artist == "Test Artist"
        assert len(result.tracks) == 1
        assert result.tracks[0].title == "Track 1"

    async def test_lookup_by_id_no_release(self, hass):
        provider = MusicBrainzProvider(hass)

        with patch("musicbrainzngs.get_release_by_id", return_value={}):
            result = await provider.async_lookup_by_id("test-mbid")

        assert result is None

    async def test_extract_artist_multiple_credits(self, hass):
        provider = MusicBrainzProvider(hass)
        release = {
            "artist-credit": [
                {"artist": {"name": "Artist A"}, "joinphrase": " & "},
                {"artist": {"name": "Artist B"}, "joinphrase": ""},
            ]
        }
        assert provider._extract_artist(release) == "Artist A & Artist B"

    async def test_extract_artist_empty(self, hass):
        provider = MusicBrainzProvider(hass)
        assert provider._extract_artist({}) == "Unknown Artist"
        assert provider._extract_artist({"artist-credit": []}) == "Unknown Artist"


class TestCalculateOffsetDistance:
    def test_identical_offsets(self):
        assert _calculate_offset_distance([150, 15150], [150, 15150]) == 0

    def test_different_offsets(self):
        assert _calculate_offset_distance([150, 15150], [150, 15200]) == 50

    def test_multiple_differences(self):
        assert _calculate_offset_distance([150, 15150, 30000], [150, 15200, 29900]) == 150

    def test_different_lengths(self):
        assert _calculate_offset_distance([150, 15150], [150, 15150, 30000]) == float("inf")


class TestFindBestMatch:
    def test_picks_release_with_closest_discid(self, hass):
        provider = MusicBrainzProvider(hass)
        our_offsets = [150, 15150]

        release_list = [
            {
                "id": "far-match",
                "medium-list": [{"disc-list": [{"offset-list": [150, 20000]}]}],
            },
            {
                "id": "close-match",
                "medium-list": [{"disc-list": [{"offset-list": [150, 15200]}]}],
            },
        ]

        result = provider._find_best_match(release_list, our_offsets)
        assert result["id"] == "close-match"

    def test_falls_back_to_first_when_no_discids(self, hass):
        provider = MusicBrainzProvider(hass)
        our_offsets = [150, 15150]

        release_list = [
            {"id": "first-no-discids", "medium-list": [{"disc-list": []}]},
            {"id": "second-no-discids", "medium-list": [{}]},
        ]

        result = provider._find_best_match(release_list, our_offsets)
        assert result["id"] == "first-no-discids"

    def test_prefers_release_with_discid_over_without(self, hass):
        provider = MusicBrainzProvider(hass)
        our_offsets = [150, 15150]

        release_list = [
            {"id": "no-discid", "medium-list": [{"disc-list": []}]},
            {"id": "has-discid", "medium-list": [{"disc-list": [{"offset-list": [150, 15200]}]}]},
        ]

        result = provider._find_best_match(release_list, our_offsets)
        assert result["id"] == "has-discid"

    async def test_lookup_uses_best_match(self, hass):
        provider = MusicBrainzProvider(hass)
        toc = _make_toc([200, 180])

        mock_result = {
            "release-list": [
                {
                    "id": "far-match",
                    "medium-list": [{"disc-list": [{"offset-list": [150, 20000]}]}],
                },
                {
                    "id": "close-match",
                    "medium-list": [{"disc-list": [{"offset-list": [150, 15200]}]}],
                },
            ]
        }

        with patch("musicbrainzngs.get_releases_by_discid", return_value=mock_result):
            result = await provider.async_lookup("fp", toc, 380)

        assert result == "close-match"


class TestCoverArtRedirects:
    @pytest.mark.parametrize("status_code", [301, 302, 307, 308])
    async def test_follows_redirect_statuses(self, hass, status_code):
        provider = MusicBrainzProvider(hass)

        mock_result = {
            "release": {
                "id": "test-mbid",
                "title": "Album",
                "artist-credit": [{"artist": {"name": "Artist"}, "joinphrase": ""}],
                "medium-list": [{"track-list": []}],
            }
        }

        mock_resp = AsyncMock()
        mock_resp.status = status_code
        mock_resp.headers = {"Location": "https://example.com/image.jpg"}
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("musicbrainzngs.get_release_by_id", return_value=mock_result), \
             patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.async_lookup_by_id("test-mbid")

        assert result is not None
        assert result.album_art_url == "https://example.com/image.jpg"

    async def test_returns_none_on_404(self, hass):
        provider = MusicBrainzProvider(hass)

        mock_result = {
            "release": {
                "id": "test-mbid",
                "title": "Album",
                "artist-credit": [{"artist": {"name": "Artist"}, "joinphrase": ""}],
                "medium-list": [{"track-list": []}],
            }
        }

        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_resp.headers = {}
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("musicbrainzngs.get_release_by_id", return_value=mock_result), \
             patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.async_lookup_by_id("test-mbid")

        assert result is not None
        assert result.album_art_url is None
