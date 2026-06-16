from pathlib import Path

import pytest

from agent_hub.agents.music_recommender.logic import (
    MusicRecommendFilters,
    _upsert_taste_artist,
    _upsert_taste_song,
    add_artist,
    add_song,
    is_collaboration_artist_name,
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
        "rock-track": TrackDetails(
            spotify_id="rock-track",
            title="Rock Song",
            artist="Rock Artist",
            artist_id="rock-artist",
            album="Rock Album",
            year=2021,
            genres=["rock"],
            energy=0.7,
            valence=0.6,
            danceability=0.5,
            tempo=120.0,
            popularity=70,
            duration_ms=210000,
            image_url=None,
            preview_url=None,
        ),
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
        "rock-artist": ArtistDetails(
            spotify_id="rock-artist",
            name="Rock Artist",
            genres=["rock"],
            popularity=75,
            followers=100000,
            image_url=None,
        ),
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
        "agent_hub.agents.music_recommender.logic.get_track_details_with_fallback",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details_with_fallback",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.collect_embed_recommendation_tracks",
        lambda *args, **kwargs: {},
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


def test_recommend_excludes_energy_from_spotify_filters(music_config, monkeypatch):
    captured: dict = {}

    def fake_get_spotify_recommendations(**kwargs):
        captured.update(kwargs)
        return ["rock-track"]

    catalog = {
        "seed": _fake_track("seed", artist_id="liked-artist"),
        "rock-track": _fake_track("rock-track", artist_id="rock-artist"),
        "rock-artist": _fake_artist("rock-artist"),
    }

    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details_with_fallback",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details_with_fallback",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.collect_embed_recommendation_tracks",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_spotify_recommendations",
        fake_get_spotify_recommendations,
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
        lambda artist_id, config=None: ["rock-artist"],
    )

    add_song("seed", "like", config=music_config)

    recommend(
        MusicRecommendFilters(
            energy_min=0.2,
            energy_max=0.8,
            include_energy=False,
            song_count=1,
            artist_count=1,
        ),
        config=music_config,
    )

    assert captured.get("energy_min") is None
    assert captured.get("energy_max") is None


def test_recommend_uses_embed_fallback_when_api_returns_no_candidates(
    music_config, monkeypatch
):
    embed_track = TrackDetails(
        spotify_id="embed-track",
        title="Embed Song",
        artist="Embed Artist",
        artist_id="embed-artist",
        album="",
        year=2020,
        genres=[],
        energy=None,
        valence=None,
        danceability=None,
        tempo=None,
        popularity=0,
        duration_ms=180000,
        image_url=None,
        preview_url=None,
    )

    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_spotify_recommendations",
        lambda **kwargs: [],
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
        lambda artist_id, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.collect_embed_recommendation_tracks",
        lambda liked_songs, liked_artists, **kwargs: {"embed-track": embed_track},
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details_with_fallback",
        lambda sid, config=None: embed_track,
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: _fake_track("seed"),
    )

    add_song("seed", "like", config=music_config)

    songs, artists = recommend(
        MusicRecommendFilters(song_count=5, artist_count=5),
        config=music_config,
    )

    assert len(songs) == 1
    assert songs[0].track.spotify_id == "embed-track"
    assert artists == []


def test_recommend_includes_out_of_range_year_when_year_excluded(music_config, monkeypatch):
    old_track = TrackDetails(
        spotify_id="old-track",
        title="Old Song",
        artist="Old Artist",
        artist_id="old-artist",
        album="",
        year=1970,
        genres=["rock"],
        energy=0.5,
        valence=0.5,
        danceability=0.5,
        tempo=100.0,
        popularity=50,
        duration_ms=180000,
        image_url=None,
        preview_url=None,
    )
    catalog = {
        "seed": _fake_track("seed", artist_id="liked-artist"),
        "old-track": old_track,
        "liked-artist": _fake_artist("liked-artist"),
    }

    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details_with_fallback",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details_with_fallback",
        lambda sid, config=None: catalog[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_spotify_recommendations",
        lambda **kwargs: ["old-track"],
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
        lambda artist_id, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.collect_embed_recommendation_tracks",
        lambda *args, **kwargs: {},
    )

    add_song("seed", "like", config=music_config)

    songs, _ = recommend(
        MusicRecommendFilters(
            year_min=1980,
            year_max=2026,
            include_year=False,
            song_count=5,
            artist_count=0,
        ),
        config=music_config,
    )
    assert {item.track.spotify_id for item in songs} == {"old-track"}


def test_recommend_excludes_liked_song_when_spotify_id_differs(music_config, monkeypatch):
    _upsert_taste_song(
        TrackDetails(
            spotify_id="pandora-abc123",
            title="Levels",
            artist="Avicii",
            artist_id="",
            album="",
            year=2011,
            genres=[],
            energy=None,
            valence=None,
            danceability=None,
            tempo=None,
            popularity=0,
            duration_ms=180000,
            image_url=None,
            preview_url=None,
        ),
        "like",
        config=music_config,
    )
    _upsert_taste_song(_fake_track("seed"), "like", config=music_config)

    duplicate = TrackDetails(
        spotify_id="spotify-real-levels",
        title="Levels",
        artist="Avicii",
        artist_id="avicii-id",
        album="True",
        year=2011,
        genres=["edm"],
        energy=0.8,
        valence=0.7,
        danceability=0.7,
        tempo=126.0,
        popularity=85,
        duration_ms=200000,
        image_url=None,
        preview_url=None,
    )
    new_track = TrackDetails(
        spotify_id="new-track",
        title="Wake Me Up",
        artist="Avicii",
        artist_id="avicii-id",
        album="True",
        year=2013,
        genres=["edm"],
        energy=0.7,
        valence=0.6,
        danceability=0.6,
        tempo=124.0,
        popularity=90,
        duration_ms=210000,
        image_url=None,
        preview_url=None,
    )

    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_spotify_recommendations",
        lambda **kwargs: [],
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
        lambda artist_id, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.collect_embed_recommendation_tracks",
        lambda liked_songs, liked_artists, **kwargs: {
            "spotify-real-levels": duplicate,
            "new-track": new_track,
        },
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details_with_fallback",
        lambda sid, config=None: {"spotify-real-levels": duplicate, "new-track": new_track}[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.fetch_new_release_candidates",
        lambda **kwargs: [],
    )

    songs, _ = recommend(
        MusicRecommendFilters(song_count=5, artist_count=0),
        config=music_config,
    )

    assert {item.track.spotify_id for item in songs} == {"new-track"}


def test_recommend_excludes_liked_artist_when_spotify_id_differs(music_config, monkeypatch):
    _upsert_taste_artist(
        ArtistDetails(
            spotify_id="pandora-artist-abc123",
            name="Embed Artist",
            genres=[],
            popularity=0,
            followers=0,
            image_url=None,
        ),
        "like",
        config=music_config,
    )
    _upsert_taste_song(_fake_track("seed"), "like", config=music_config)

    embed_track = TrackDetails(
        spotify_id="embed-track",
        title="Embed Song",
        artist="Embed Artist",
        artist_id="embed-artist",
        album="",
        year=2020,
        genres=[],
        energy=None,
        valence=None,
        danceability=None,
        tempo=None,
        popularity=0,
        duration_ms=180000,
        image_url=None,
        preview_url=None,
    )
    other_artist = ArtistDetails(
        spotify_id="other-artist",
        name="Other Artist",
        genres=["rock"],
        popularity=50,
        followers=1000,
        image_url=None,
    )

    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_spotify_recommendations",
        lambda **kwargs: [],
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
        lambda artist_id, config=None: ["other-artist"],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.collect_embed_recommendation_tracks",
        lambda liked_songs, liked_artists, **kwargs: {"embed-track": embed_track},
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details_with_fallback",
        lambda sid, config=None: embed_track,
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details_with_fallback",
        lambda sid, config=None: {
            "embed-artist": ArtistDetails(
                spotify_id="embed-artist",
                name="Embed Artist",
                genres=[],
                popularity=50,
                followers=1000,
                image_url=None,
            ),
            "other-artist": other_artist,
        }[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.fetch_new_release_candidates",
        lambda **kwargs: [],
    )

    _, artists = recommend(
        MusicRecommendFilters(song_count=5, artist_count=5),
        config=music_config,
    )

    assert {item.artist.spotify_id for item in artists} == {"other-artist"}


def test_collect_collaborator_artist_candidates_excludes_seed_artists():
    from agent_hub.agents.music_recommender.spotify import collect_collaborator_artist_candidates

    class Song:
        def __init__(self, spotify_id: str, artist: str = ""):
            self.spotify_id = spotify_id
            self.artist = artist

    cache = {
        "collab-track": TrackDetails(
            spotify_id="collab-track",
            title="Collab Song",
            artist="Seed Artist, Guest Artist",
            artist_id="seed-artist",
            album="",
            year=2020,
            genres=[],
            energy=None,
            valence=None,
            danceability=None,
            tempo=None,
            popularity=0,
            duration_ms=180000,
            image_url=None,
            preview_url=None,
        )
    }

    def fake_fetch(track_id: str):
        return {
            "solo-track": ["seed-artist"],
            "collab-track": ["seed-artist", "guest-artist"],
        }[track_id]

    import agent_hub.agents.music_recommender.spotify as spotify_mod

    original = spotify_mod.fetch_track_artist_ids_from_embed
    spotify_mod.fetch_track_artist_ids_from_embed = fake_fetch
    try:
        candidates = collect_collaborator_artist_candidates(
            [Song("solo-track"), Song("collab-track", "Seed Artist, Guest Artist")],
            cache,
            {"seed-artist"},
            max_liked_track_lookups=10,
        )
    finally:
        spotify_mod.fetch_track_artist_ids_from_embed = original

    assert candidates == ["guest-artist"]


def test_is_collaboration_artist_name_detects_multi_artist_credits():
    assert is_collaboration_artist_name("Kygo & Selena Gomez")
    assert is_collaboration_artist_name("DJ Snake, Rick Ross & Rich Brian")
    assert is_collaboration_artist_name("David Guetta & Bebe Rexha explicit")
    assert is_collaboration_artist_name("Artist feat. Guest")
    assert not is_collaboration_artist_name("Andy Frasco & The U.N.")
    assert not is_collaboration_artist_name("Avicii")


def test_remove_collaboration_liked_artists(music_config, monkeypatch):
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_artist_details",
        lambda sid, config=None: ArtistDetails(
            spotify_id=sid,
            name={"solo": "Avicii", "collab": "Kygo & Selena Gomez"}[sid],
            genres=[],
            popularity=0,
            followers=0,
            image_url=None,
        ),
    )
    add_artist("solo", "like", config=music_config)
    add_artist("collab", "like", config=music_config)

    from agent_hub.agents.music_recommender.logic import remove_collaboration_liked_artists

    removed = remove_collaboration_liked_artists(config=music_config)
    remaining = {a.spotify_id for a in list_liked_artists(music_config)}

    assert len(removed) == 1
    assert removed[0].spotify_id == "collab"
    assert remaining == {"solo"}


def test_song_variation_key_strips_remix_and_live_suffixes():
    from agent_hub.agents.music_recommender.logic import _song_variation_key

    radio = _song_variation_key("Sweet Lovin' (Radio Edit)", "Sigala")
    remix = _song_variation_key("Sweet Lovin' (Steve Smart Remix)", "Sigala")
    live = _song_variation_key("He's Gone - Live at Richmond Coliseum, Richmond, VA", "Grateful Dead")
    studio = _song_variation_key("He's Gone", "Grateful Dead")

    assert radio == remix
    assert live == studio


def test_track_is_liked_matches_song_variations(music_config):
    from agent_hub.agents.music_recommender.logic import _track_is_liked, _upsert_taste_song

    _upsert_taste_song(
        TrackDetails(
            spotify_id="pandora-sweet-lovin",
            title="Sweet Lovin' (Radio Edit)",
            artist="Sigala",
            artist_id="",
            album="",
            year=2015,
            genres=[],
            energy=None,
            valence=None,
            danceability=None,
            tempo=None,
            popularity=0,
            duration_ms=180000,
            image_url=None,
            preview_url=None,
        ),
        "like",
        config=music_config,
    )
    liked = list_liked_songs(music_config)
    remix = TrackDetails(
        spotify_id="spotify-remix",
        title="Sweet Lovin' (Steve Smart Remix)",
        artist="Sigala",
        artist_id="sigala",
        album="",
        year=2015,
        genres=["dance"],
        energy=0.7,
        valence=0.8,
        danceability=0.7,
        tempo=124.0,
        popularity=60,
        duration_ms=200000,
        image_url=None,
        preview_url=None,
    )
    different = TrackDetails(
        spotify_id="spotify-other",
        title="Easy Love",
        artist="Sigala",
        artist_id="sigala",
        album="",
        year=2015,
        genres=["dance"],
        energy=0.7,
        valence=0.8,
        danceability=0.7,
        tempo=124.0,
        popularity=60,
        duration_ms=200000,
        image_url=None,
        preview_url=None,
    )

    assert _track_is_liked(remix, liked)
    assert not _track_is_liked(different, liked)


def test_recommend_excludes_song_variation_of_liked_track(music_config, monkeypatch):
    from agent_hub.agents.music_recommender.logic import _upsert_taste_song

    _upsert_taste_song(
        TrackDetails(
            spotify_id="pandora-be-ok",
            title="Be Ok",
            artist="Party Favor",
            artist_id="",
            album="",
            year=2019,
            genres=[],
            energy=None,
            valence=None,
            danceability=None,
            tempo=None,
            popularity=0,
            duration_ms=180000,
            image_url=None,
            preview_url=None,
        ),
        "like",
        config=music_config,
    )
    _upsert_taste_song(_fake_track("seed"), "like", config=music_config)

    variation = TrackDetails(
        spotify_id="be-ok-extended",
        title="Be Ok (Extended Mix)",
        artist="Party Favor explicit",
        artist_id="party-favor",
        album="",
        year=2019,
        genres=["edm"],
        energy=0.8,
        valence=0.7,
        danceability=0.7,
        tempo=128.0,
        popularity=50,
        duration_ms=240000,
        image_url=None,
        preview_url=None,
    )
    new_song = TrackDetails(
        spotify_id="new-song",
        title="Satisfaction",
        artist="Party Favor",
        artist_id="party-favor",
        album="",
        year=2020,
        genres=["edm"],
        energy=0.8,
        valence=0.7,
        danceability=0.7,
        tempo=128.0,
        popularity=50,
        duration_ms=200000,
        image_url=None,
        preview_url=None,
    )

    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_spotify_recommendations",
        lambda **kwargs: [],
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
        lambda artist_id, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.collect_embed_recommendation_tracks",
        lambda liked_songs, liked_artists, **kwargs: {
            "be-ok-extended": variation,
            "new-song": new_song,
        },
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.get_track_details_with_fallback",
        lambda sid, config=None: {"be-ok-extended": variation, "new-song": new_song}[sid],
    )
    monkeypatch.setattr(
        "agent_hub.agents.music_recommender.logic.fetch_new_release_candidates",
        lambda **kwargs: [],
    )

    songs, _ = recommend(
        MusicRecommendFilters(song_count=5, artist_count=0),
        config=music_config,
    )

    assert {item.track.spotify_id for item in songs} == {"new-song"}
