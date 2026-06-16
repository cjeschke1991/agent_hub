from __future__ import annotations

import math
from dataclasses import dataclass

from agent_hub.core.config import MusicRecommenderWeights


@dataclass
class SongScoreBreakdown:
    genre: float
    audio_features: float
    artist_affinity: float
    year: float
    popularity: float
    total: float

    def as_labels(self) -> dict[str, float]:
        return {
            "Genre": self.genre,
            "Audio": self.audio_features,
            "Artist": self.artist_affinity,
            "Year": self.year,
            "Popularity": self.popularity,
        }


@dataclass
class ArtistScoreBreakdown:
    genre: float
    related_artists: float
    popularity: float
    era: float
    total: float

    def as_labels(self) -> dict[str, float]:
        return {
            "Genre": self.genre,
            "Related": self.related_artists,
            "Popularity": self.popularity,
            "Era": self.era,
        }


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right) * 100.0


def _genre_overlap(
    candidate_genres: list[str],
    liked_genres: set[str],
    disliked_genres: set[str],
) -> float:
    cg = set(g.lower() for g in candidate_genres)
    if not cg:
        return 0.0
    match = _overlap_score(cg, liked_genres)
    penalty = len(cg & disliked_genres) / max(len(cg), 1) * 40.0
    return max(0.0, min(100.0, match - penalty))


def _audio_distance(
    energy: float | None,
    valence: float | None,
    danceability: float | None,
    liked_energy: list[float],
    liked_valence: list[float],
    liked_danceability: list[float],
    *,
    include_energy: bool = True,
    include_valence: bool = True,
) -> float:
    """Similarity score 0-100 based on Euclidean distance from liked centroid."""
    dims: list[tuple[float | None, list[float]]] = []
    if include_energy:
        dims.append((energy, liked_energy))
    if include_valence:
        dims.append((valence, liked_valence))
    dims.append((danceability, liked_danceability))
    valid = [(v, lst) for v, lst in dims if v is not None and lst]
    if not valid:
        return 0.0
    sq_sum = 0.0
    for v, lst in valid:
        centroid = _avg(lst)
        sq_sum += (v - centroid) ** 2
    distance = math.sqrt(sq_sum / len(valid))
    return max(0.0, 100.0 - distance * 150.0)


def song_score(
    candidate_genres: list[str],
    candidate_energy: float | None,
    candidate_valence: float | None,
    candidate_danceability: float | None,
    candidate_artist_id: str,
    candidate_year: int | None,
    candidate_popularity: int,
    liked_genres: set[str],
    disliked_genres: set[str],
    liked_energy: list[float],
    liked_valence: list[float],
    liked_danceability: list[float],
    liked_artist_ids: set[str],
    related_artist_ids: set[str],
    year_min: int,
    year_max: int,
    liked_years: list[int],
    weights: MusicRecommenderWeights,
    *,
    include_energy: bool = True,
    include_valence: bool = True,
) -> SongScoreBreakdown:
    genre = _genre_overlap(candidate_genres, liked_genres, disliked_genres)

    audio = _audio_distance(
        candidate_energy,
        candidate_valence,
        candidate_danceability,
        liked_energy,
        liked_valence,
        liked_danceability,
        include_energy=include_energy,
        include_valence=include_valence,
    )

    if candidate_artist_id and candidate_artist_id in liked_artist_ids:
        artist_affinity = 100.0
    elif candidate_artist_id and candidate_artist_id in related_artist_ids:
        artist_affinity = 60.0
    else:
        artist_affinity = 0.0

    if candidate_year is None or candidate_year < year_min or candidate_year > year_max:
        year = 0.0
    elif liked_years:
        avg_year = _avg([float(y) for y in liked_years])
        distance = abs(candidate_year - avg_year)
        span = max(year_max - year_min, 1)
        year = 60.0 + max(0.0, 1.0 - distance / span) * 40.0
    else:
        year = 100.0

    pop = min(100.0, float(candidate_popularity))

    total = round(
        genre * weights.song_genre
        + audio * weights.song_audio_features
        + artist_affinity * weights.song_artist_affinity
        + year * weights.song_year
        + pop * weights.song_popularity,
        1,
    )
    return SongScoreBreakdown(
        genre=genre,
        audio_features=audio,
        artist_affinity=artist_affinity,
        year=year,
        popularity=pop,
        total=total,
    )


def artist_score(
    candidate_genres: list[str],
    candidate_spotify_id: str,
    candidate_popularity: int,
    candidate_related_ids: list[str],
    liked_genres: set[str],
    disliked_genres: set[str],
    liked_artist_ids: set[str],
    year_min: int,
    year_max: int,
    weights: MusicRecommenderWeights,
) -> ArtistScoreBreakdown:
    genre = _genre_overlap(candidate_genres, liked_genres, disliked_genres)

    related_set = set(candidate_related_ids)
    overlap = len(related_set & liked_artist_ids)
    related = min(100.0, overlap * 30.0)

    pop = min(100.0, float(candidate_popularity))

    era = 50.0

    total = round(
        genre * weights.artist_genre
        + related * weights.artist_related_artists
        + pop * weights.artist_popularity
        + era * weights.artist_era,
        1,
    )
    return ArtistScoreBreakdown(
        genre=genre,
        related_artists=related,
        popularity=pop,
        era=era,
        total=total,
    )
