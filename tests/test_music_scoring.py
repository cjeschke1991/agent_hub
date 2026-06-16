from agent_hub.agents.music_recommender.scoring import (
    artist_score,
    song_score,
)
from agent_hub.core.config import MusicRecommenderWeights


def _weights() -> MusicRecommenderWeights:
    return MusicRecommenderWeights()


def test_song_score_liked_artist_boosts():
    scr = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.7,
        candidate_valence=0.6,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=2020,
        candidate_popularity=70,
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_energy=[0.7],
        liked_valence=[0.6],
        liked_danceability=[0.5],
        liked_artist_ids={"a1"},
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[2018],
        weights=_weights(),
    )
    assert scr.artist_affinity == 100.0
    assert scr.total > 0


def test_song_score_disliked_genre_penalizes():
    scr = song_score(
        candidate_genres=["country"],
        candidate_energy=0.5,
        candidate_valence=0.5,
        candidate_danceability=0.5,
        candidate_artist_id="a99",
        candidate_year=2020,
        candidate_popularity=50,
        liked_genres={"rock"},
        disliked_genres={"country"},
        liked_energy=[0.5],
        liked_valence=[0.5],
        liked_danceability=[0.5],
        liked_artist_ids=set(),
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[2018],
        weights=_weights(),
    )
    assert scr.genre < 10


def test_song_score_out_of_year_range():
    scr = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.7,
        candidate_valence=0.6,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=1950,
        candidate_popularity=70,
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_energy=[0.7],
        liked_valence=[0.6],
        liked_danceability=[0.5],
        liked_artist_ids=set(),
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[2000],
        weights=_weights(),
    )
    assert scr.year == 0.0


def test_artist_score_related_liked():
    scr = artist_score(
        candidate_genres=["rock"],
        candidate_spotify_id="cand1",
        candidate_popularity=80,
        candidate_related_ids=["a1", "a2", "a3"],
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_artist_ids={"a1", "a2"},
        year_min=1980,
        year_max=2026,
        weights=_weights(),
    )
    assert scr.related_artists > 0
    assert scr.total > 0


def test_artist_score_no_overlap():
    scr = artist_score(
        candidate_genres=["jazz"],
        candidate_spotify_id="cand2",
        candidate_popularity=40,
        candidate_related_ids=["x1", "x2"],
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_artist_ids={"a1"},
        year_min=1980,
        year_max=2026,
        weights=_weights(),
    )
    assert scr.related_artists == 0.0
