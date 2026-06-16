from agent_hub.agents.music_recommender.spotify import parse_playlist_id


def test_parse_playlist_id_from_url():
    url = "https://open.spotify.com/playlist/2zto3gUYnnFbmS7OrHDmUF?si=abc"
    assert parse_playlist_id(url) == "2zto3gUYnnFbmS7OrHDmUF"


def test_parse_playlist_id_from_uri():
    assert parse_playlist_id("spotify:playlist:abc123") == "abc123"


def test_parse_playlist_id_raw():
    assert parse_playlist_id("abc123") == "abc123"
