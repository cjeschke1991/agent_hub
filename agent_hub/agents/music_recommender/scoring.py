from __future__ import annotations

import math
from dataclasses import dataclass

from agent_hub.core.config import MusicRecommenderWeights, MusicZoneWeights


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


def taste_text_similarity(
    title: str,
    artist: str,
    liked_songs: list[tuple[str, str]],
) -> float:
    """Match candidate title/artist against liked song metadata (0-100)."""
    if not liked_songs:
        return 0.0
    title_n = title.lower().strip()
    artist_parts = [a.strip().lower() for a in artist.split(",") if a.strip()]
    best = 0.0
    for liked_title, liked_artist in liked_songs:
        lt = liked_title.lower().strip()
        la = liked_artist.lower().strip()
        if title_n and lt and (title_n == lt or title_n in lt or lt in title_n):
            best = max(best, 100.0 if title_n == lt else 85.0)
        if la and artist_parts:
            if la in artist_parts or any(
                part in la or la in part for part in artist_parts
            ):
                best = max(best, 70.0)
            elif any(part in artist for part in la.split("&")):
                best = max(best, 55.0)
    return best


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
    include_year: bool = True,
    taste_text_match: float = 0.0,
    explicit_liked_artist_ids: set[str] | None = None,
    source_rank: int | None = None,
    zone_weights: MusicZoneWeights | None = None,
) -> SongScoreBreakdown:
    genre = max(
        _genre_overlap(candidate_genres, liked_genres, disliked_genres),
        taste_text_match,
    )

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

    explicit_ids = explicit_liked_artist_ids if explicit_liked_artist_ids is not None else liked_artist_ids
    if candidate_artist_id and candidate_artist_id in explicit_ids:
        artist_affinity = 100.0
    elif candidate_artist_id and candidate_artist_id in liked_artist_ids:
        artist_affinity = 65.0
    elif candidate_artist_id and candidate_artist_id in related_artist_ids:
        artist_affinity = 60.0
    else:
        artist_affinity = 0.0

    if include_year:
        if candidate_year is None or candidate_year < year_min or candidate_year > year_max:
            year = 0.0
        elif liked_years:
            avg_year = _avg([float(y) for y in liked_years])
            distance = abs(candidate_year - avg_year)
            span = max(year_max - year_min, 1)
            year = 60.0 + max(0.0, 1.0 - distance / span) * 40.0
        else:
            year = 100.0
        year_weight = zone_weights.song_year if zone_weights else weights.song_year
    else:
        year = 0.0
        year_weight = 0.0

    pop = min(100.0, float(candidate_popularity))
    if pop == 0 and source_rank is not None:
        pop = max(15.0, 100.0 - source_rank * 8)

    w_genre = zone_weights.song_genre if zone_weights else weights.song_genre
    w_audio = zone_weights.song_audio_features if zone_weights else weights.song_audio_features
    w_affinity = zone_weights.song_artist_affinity if zone_weights else weights.song_artist_affinity
    w_pop_raw = zone_weights.song_popularity if zone_weights else weights.song_popularity

    # Negative popularity weight = anti-popularity bias (Wild Card zone).
    # We invert the popularity score so lower popularity yields a higher contribution.
    if w_pop_raw < 0:
        pop_contrib = (100.0 - pop) * abs(w_pop_raw)
    else:
        pop_contrib = pop * w_pop_raw

    total_raw = (
        genre * w_genre
        + audio * w_audio
        + artist_affinity * w_affinity
        + year * year_weight
        + pop_contrib
    )
    total = round(max(0.0, total_raw), 1)

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
    *,
    embed_liked_song_count: int = 0,
) -> ArtistScoreBreakdown:
    genre = _genre_overlap(candidate_genres, liked_genres, disliked_genres)

    related_set = set(candidate_related_ids)
    overlap = len(related_set & liked_artist_ids)
    # embed_liked_song_count: # of embed top-tracks that belong to this artist
    # (proxy for relatedness when the Web API related-artists endpoint is unavailable)
    related = max(
        min(100.0, overlap * 30.0),
        min(100.0, embed_liked_song_count * 25.0),
    )

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
