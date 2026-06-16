from pathlib import Path

import pytest

from agent_hub.agents.music_recommender.logic import (
    MusicRecommendFilters,
    add_artist,
    add_song,
    add_artist_to_wishlist,
    add_song_to_wishlist,
    get_spotify_genres,
    list_disliked_artists,
    list_disliked_songs,
    list_liked_artists,
    list_liked_songs,
    list_wishlist_artists,
    list_wishlist_songs,
    recommend,
    remove_artist,
    remove_song,
    remove_artist_from_wishlist,
    remove_song_from_wishlist,
)
from agent_hub.agents.music_recommender.spotify import ArtistDetails, TrackDetails
from agent_hub.core.config import HubConfig, SpotifyConfig


@pytest.fixture
def music_config(tmp_path: Path) -> HubConfig:
    return HubConfig(
        data_dir=tmp_path,
        spotify=SpotifyConfig(client_id="id", client_secret="secret"),
    )


def _fake_track(spotify_id: str = "t1", artist_id: str = "a1") -> TrackDetails:
    return TrackDetails(
        spotify_id=spotify_id,
        title="Test Song",
        artist="Test Artist",
        artist_id=artist_id,
        album="Test Album",
        year=2020,
        genres=["rock", "indie"],
        energy=0.7,
        valence=0.6,
        danceability=0.5,
        tempo=120.0,
        popularity=70,
        duration_ms=210000,
        image_url=None,
        preview_url=None,
    )


def _fake_artist(spotify_id: str = "a1") -> ArtistDetails:
    return ArtistDetails(
        spotify_id=spotify_id,
        name="Test Artist",
        genres=["rock"],
        popularity=75,
        followers=100000,
        image_url=None,
    )


def test_add_and_list_liked_song(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: _fake_track(sid),
    )
    song = add_song("t1", "like", config=music_config)
    assert song.title == "Test Song"
    assert song.sentiment == "like"

    liked = list_liked_songs(music_config)
    assert len(liked) == 1
    assert liked[0].spotify_id == "t1"

    disliked = list_disliked_songs(music_config)
    assert disliked == []


def test_add_and_list_disliked_song(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: _fake_track(sid),
    )
    add_song("t2", "dislike", config=music_config)
    assert list_disliked_songs(music_config)[0].spotify_id == "t2"
    assert list_liked_songs(music_config) == []


def test_remove_song(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: _fake_track(sid),
    )
    add_song("t3", "like", config=music_config)
    remove_song("t3", config=music_config)
    assert list_liked_songs(music_config) == []


def test_add_and_list_liked_artist(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: _fake_artist(sid),
    )
    artist = add_artist("a1", "like", config=music_config)
    assert artist.name == "Test Artist"
    assert artist.sentiment == "like"

    liked = list_liked_artists(music_config)
    assert len(liked) == 1
    assert liked[0].spotify_id == "a1"


def test_remove_artist(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: _fake_artist(sid),
    )
    add_artist("a2", "like", config=music_config)
    remove_artist("a2", config=music_config)
    assert list_liked_artists(music_config) == []


def test_song_wishlist(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: _fake_track(sid),
    )
    add_song_to_wishlist("t4", config=music_config)
    wl = list_wishlist_songs(music_config)
    assert len(wl) == 1
    assert wl[0].spotify_id == "t4"

    remove_song_from_wishlist("t4", config=music_config)
    assert list_wishlist_songs(music_config) == []


def test_artist_wishlist(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: _fake_artist(sid),
    )
    add_artist_to_wishlist("a3", config=music_config)
    wl = list_wishlist_artists(music_config)
    assert len(wl) == 1
    assert wl[0].spotify_id == "a3"

    remove_artist_from_wishlist("a3", config=music_config)
    assert list_wishlist_artists(music_config) == []


def test_update_sentiment_on_re_add(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: _fake_track(sid),
    )
    add_song("t5", "like", config=music_config)
    add_song("t5", "dislike", config=music_config)
    liked = list_liked_songs(music_config)
    disliked = list_disliked_songs(music_config)
    assert liked == []
    assert len(disliked) == 1
    assert disliked[0].spotify_id == "t5"


def test_get_spotify_genres(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_available_genre_seeds",
        lambda config=None: ["rock", "pop", "jazz"],
    )
    assert get_spotify_genres(music_config) == ["rock", "pop", "jazz"]


def test_recommend_filters_by_selected_genre(music_config, monkeypatch):
    catalog = {
        "seed": _fake_track("seed", artist_id="liked-artist"),
        "rock-track": _fake_track("rock-track", artist_id="rock-artist"),
        "pop-track": TrackDetails(
            spotify_id="pop-track",
            title="Pop Song",
            artist="Pop Artist",
            artist_id="pop-artist",
            album="Pop Album",
            year=2021,
            genres=["pop"],
            energy=0.5,
            valence=0.5,
            danceability=0.5,
            tempo=110.0,
            popularity=60,
            duration_ms=200000,
            image_url=None,
            preview_url=None,
        ),
        "rock-artist": _fake_artist("rock-artist"),
        "pop-artist": ArtistDetails(
            spotify_id="pop-artist",
            name="Pop Artist",
            genres=["pop"],
            popularity=70,
            followers=50000,
            image_url=None,
        ),
        "liked-artist": _fake_artist("liked-artist"),
    }

    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_spotify_recommendations",
        lambda **kwargs: ["rock-track", "pop-track"],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_top_track_ids",
        lambda artist_id, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.search_tracks_by_genre",
        lambda genre, limit=20, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_related_artist_ids",
        lambda artist_id, config=None: ["rock-artist", "pop-artist"],
    )

    add_song("seed", "like", config=music_config)
    add_artist("liked-artist", "like", config=music_config)

    songs, artists = recommend(
        MusicRecommendFilters(
            genre_names=["rock"],
            song_count=5,
            artist_count=5,
        ),
        config=music_config,
    )

    assert {item.track.spotify_id for item in songs} == {"rock-track"}
    assert {item.artist.spotify_id for item in artists} == {"rock-artist"}
