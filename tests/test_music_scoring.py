from agent_hub.agents.music_recommender.scoring import (
    artist_score,
    song_score,
    taste_text_similarity,
)
from agent_hub.core.config import MusicRecommenderWeights, MusicZoneWeights


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


def test_song_score_excluding_energy_ignores_energy_dimension():
    with_energy = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.9,
        candidate_valence=0.6,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=2020,
        candidate_popularity=70,
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_energy=[0.2],
        liked_valence=[0.6],
        liked_danceability=[0.5],
        liked_artist_ids=set(),
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[2018],
        weights=_weights(),
        include_energy=True,
    )
    without_energy = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.9,
        candidate_valence=0.6,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=2020,
        candidate_popularity=70,
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_energy=[0.2],
        liked_valence=[0.6],
        liked_danceability=[0.5],
        liked_artist_ids=set(),
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[2018],
        weights=_weights(),
        include_energy=False,
    )
    assert without_energy.audio_features > with_energy.audio_features


def test_song_score_excluding_valence_ignores_mood_dimension():
    with_valence = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.7,
        candidate_valence=0.9,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=2020,
        candidate_popularity=70,
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_energy=[0.7],
        liked_valence=[0.2],
        liked_danceability=[0.5],
        liked_artist_ids=set(),
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[2018],
        weights=_weights(),
        include_valence=True,
    )
    without_valence = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.7,
        candidate_valence=0.9,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=2020,
        candidate_popularity=70,
        liked_genres={"rock"},
        disliked_genres=set(),
        liked_energy=[0.7],
        liked_valence=[0.2],
        liked_danceability=[0.5],
        liked_artist_ids=set(),
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[2018],
        weights=_weights(),
        include_valence=False,
    )
    assert without_valence.audio_features > with_valence.audio_features


def test_song_score_excluding_year_ignores_year_penalty():
    with_year = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.7,
        candidate_valence=0.6,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=1970,
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
        liked_years=[2020],
        weights=_weights(),
        include_year=True,
    )
    without_year = song_score(
        candidate_genres=["rock"],
        candidate_energy=0.7,
        candidate_valence=0.6,
        candidate_danceability=0.5,
        candidate_artist_id="a1",
        candidate_year=1970,
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
        liked_years=[2020],
        weights=_weights(),
        include_year=False,
    )
    assert with_year.year == 0.0
    assert without_year.year == 0.0
    assert without_year.total >= with_year.total


def test_taste_text_similarity_matches_liked_metadata():
    liked = [("Levels", "Avicii"), ("Titanium", "David Guetta")]
    assert taste_text_similarity("Levels", "Avicii", liked) == 100.0
    assert taste_text_similarity("Levels (Radio Edit)", "Avicii", liked) >= 85.0
    assert taste_text_similarity("Other Song", "Avicii", liked) == 70.0


def test_song_score_varies_by_embed_source_rank():
    high_rank = song_score(
        candidate_genres=[],
        candidate_energy=None,
        candidate_valence=None,
        candidate_danceability=None,
        candidate_artist_id="a1",
        candidate_year=None,
        candidate_popularity=0,
        liked_genres=set(),
        disliked_genres=set(),
        liked_energy=[],
        liked_valence=[],
        liked_danceability=[],
        liked_artist_ids={"a1"},
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[],
        weights=_weights(),
        source_rank=0,
    )
    low_rank = song_score(
        candidate_genres=[],
        candidate_energy=None,
        candidate_valence=None,
        candidate_danceability=None,
        candidate_artist_id="a1",
        candidate_year=None,
        candidate_popularity=0,
        liked_genres=set(),
        disliked_genres=set(),
        liked_energy=[],
        liked_valence=[],
        liked_danceability=[],
        liked_artist_ids={"a1"},
        related_artist_ids=set(),
        year_min=1980,
        year_max=2026,
        liked_years=[],
        weights=_weights(),
        source_rank=9,
    )
    assert high_rank.total > low_rank.total


def test_zone_safe_weights_boost_artist_affinity():
    """Safe zone weights heavy on artist_affinity yield higher score for known artist."""
    safe_zone = MusicZoneWeights(
        song_genre=0.20, song_audio_features=0.25,
        song_artist_affinity=0.35, song_year=0.10, song_popularity=0.10,
    )
    base_kwargs = dict(
        candidate_genres=["rock"], candidate_energy=0.7, candidate_valence=0.6,
        candidate_danceability=0.5, candidate_year=2020, candidate_popularity=50,
        liked_genres={"rock"}, disliked_genres=set(), liked_energy=[0.7],
        liked_valence=[0.6], liked_danceability=[0.5],
        related_artist_ids=set(), year_min=1980, year_max=2026,
        liked_years=[2020], weights=_weights(),
    )
    liked = song_score(candidate_artist_id="a1", liked_artist_ids={"a1"},
                       zone_weights=safe_zone, **base_kwargs)
    unknown = song_score(candidate_artist_id="unk", liked_artist_ids={"a1"},
                         zone_weights=safe_zone, **base_kwargs)
    assert liked.total > unknown.total


def test_zone_wild_card_anti_popularity_bias():
    """Wild card zone should score a low-popularity track higher than a high-popularity one."""
    wild_zone = MusicZoneWeights(
        song_genre=0.20, song_audio_features=0.25,
        song_artist_affinity=0.00, song_year=0.05, song_popularity=-0.15,
    )
    base_kwargs = dict(
        candidate_genres=["indie"], candidate_energy=0.6, candidate_valence=0.5,
        candidate_danceability=0.5, candidate_artist_id="unk", candidate_year=2024,
        liked_genres={"indie"}, disliked_genres=set(), liked_energy=[0.6],
        liked_valence=[0.5], liked_danceability=[0.5],
        liked_artist_ids=set(), related_artist_ids=set(), year_min=1980, year_max=2026,
        liked_years=[2022], weights=_weights(), zone_weights=wild_zone,
    )
    low_pop = song_score(candidate_popularity=5, **base_kwargs)
    high_pop = song_score(candidate_popularity=95, **base_kwargs)
    assert low_pop.total > high_pop.total


def test_zone_stretch_ignores_artist_affinity():
    """Stretch zone weights zero out artist_affinity contribution."""
    stretch_zone = MusicZoneWeights(
        song_genre=0.45, song_audio_features=0.30,
        song_artist_affinity=0.00, song_year=0.10, song_popularity=0.15,
    )
    base_kwargs = dict(
        candidate_genres=["pop"], candidate_energy=0.6, candidate_valence=0.7,
        candidate_danceability=0.6, candidate_year=2023, candidate_popularity=60,
        liked_genres={"pop"}, disliked_genres=set(), liked_energy=[0.6],
        liked_valence=[0.7], liked_danceability=[0.6],
        related_artist_ids=set(), year_min=1980, year_max=2026,
        liked_years=[2020], weights=_weights(), zone_weights=stretch_zone,
    )
    liked_artist = song_score(candidate_artist_id="a1", liked_artist_ids={"a1"}, **base_kwargs)
    unknown_artist = song_score(candidate_artist_id="unk", liked_artist_ids={"a1"}, **base_kwargs)
    assert liked_artist.total == unknown_artist.total


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
