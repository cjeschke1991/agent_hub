from agent_hub.agents.music_recommender.spotify import (
    SpotifyWebApiUnavailableError,
    parse_artist_id,
    parse_playlist_id,
    parse_track_id,
    search_artists,
    search_tracks,
)
import pytest
import urllib.request


def test_parse_playlist_id_from_url():
    url = "https://open.spotify.com/playlist/2zto3gUYnnFbmS7OrHDmUF?si=abc"
    assert parse_playlist_id(url) == "2zto3gUYnnFbmS7OrHDmUF"


def test_parse_playlist_id_from_uri():
    assert parse_playlist_id("spotify:playlist:abc123") == "abc123"


def test_parse_playlist_id_raw():
    assert parse_playlist_id("abc123") == "abc123"


def test_parse_track_id_from_url():
    url = "https://open.spotify.com/track/4u7Ene62tUx6OzPlJuKPNY?si=abc"
    assert parse_track_id(url) == "4u7Ene62tUx6OzPlJuKPNY"


def test_parse_track_id_from_uri():
    assert parse_track_id("spotify:track:4u7Ene62tUx6OzPlJuKPNY") == "4u7Ene62tUx6OzPlJuKPNY"


def test_parse_artist_id_from_url():
    url = "https://open.spotify.com/artist/54SHZF2YS3W87xuJKSvOVf"
    assert parse_artist_id(url) == "54SHZF2YS3W87xuJKSvOVf"


def test_search_tracks_requires_web_api_for_text_query(monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.spotify.spotify_web_api_available",
        lambda config=None: False,
    )

    with pytest.raises(SpotifyWebApiUnavailableError):
        search_tracks("bohemian rhapsody")


def test_search_artists_requires_web_api_for_text_query(monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.spotify.spotify_web_api_available",
        lambda config=None: False,
    )

    with pytest.raises(SpotifyWebApiUnavailableError):
        search_artists("queen")


def test_is_transient_network_error_detects_connection_reset():
    from agent_hub.agents.music_recommender.spotify import _is_transient_network_error

    assert _is_transient_network_error(ConnectionResetError(54, "Connection reset by peer"))
    assert _is_transient_network_error(TimeoutError())
    assert not _is_transient_network_error(ValueError("nope"))


def test_fetch_embed_retries_connection_reset(monkeypatch):
    import agent_hub.agents.music_recommender.spotify as spotify_mod

    spotify_mod._embed_page_cache.clear()
    calls = {"n": 0}
    payload_html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"state":{"data":{"entity":{"title":"Song","uri":"spotify:track:abc12345678901234567890","subtitle":"Artist","duration":1000}}}}}}'
        "</script>"
    )

    class FakeResponse:
        def read(self):
            return payload_html.encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=30):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionResetError(54, "Connection reset by peer")
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(spotify_mod.time, "sleep", lambda _seconds: None)

    data = spotify_mod._fetch_embed_next_data("track/abc12345678901234567890")
    assert "props" in data
    assert calls["n"] == 3
