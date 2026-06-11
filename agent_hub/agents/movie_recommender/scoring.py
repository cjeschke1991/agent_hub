from __future__ import annotations

from dataclasses import dataclass

from agent_hub.agents.movie_recommender.tmdb import MovieDetails
from agent_hub.core.config import MovieRecommenderWeights


@dataclass
class ScoreBreakdown:
    genre: float
    cast_director: float
    year: float
    rating: float
    keywords: float
    total: float

    def as_labels(self) -> dict[str, float]:
        return {
            "Genre": self.genre,
            "Cast/Director": self.cast_director,
            "Year": self.year,
            "Rating": self.rating,
            "Keywords": self.keywords,
        }


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right) * 100


def _liked_genres(liked: list[MovieDetails]) -> set[str]:
    genres: set[str] = set()
    for movie in liked:
        genres.update(movie.genres)
    return genres


def _disliked_genres(disliked: list[MovieDetails]) -> set[str]:
    genres: set[str] = set()
    for movie in disliked:
        genres.update(movie.genres)
    return genres


def genre_score(candidate: MovieDetails, liked: list[MovieDetails], disliked: list[MovieDetails]) -> float:
    if not liked:
        return 0.0
    liked_set = _liked_genres(liked)
    disliked_set = _disliked_genres(disliked)
    candidate_genres = set(candidate.genres)
    if not candidate_genres:
        return 0.0
    match = _overlap_score(candidate_genres, liked_set)
    penalty = len(candidate_genres & disliked_set) / max(len(candidate_genres), 1) * 40
    return max(0.0, min(100.0, match - penalty))


def cast_director_score(candidate: MovieDetails, liked: list[MovieDetails]) -> float:
    if not liked:
        return 0.0
    liked_people: set[str] = set()
    for movie in liked:
        if movie.director:
            liked_people.add(movie.director.lower())
        liked_people.update(name.lower() for name in movie.cast)
    candidate_people: set[str] = set()
    if candidate.director:
        candidate_people.add(candidate.director.lower())
    candidate_people.update(name.lower() for name in candidate.cast)
    if not candidate_people:
        return 0.0
    overlap = len(liked_people & candidate_people)
    return min(100.0, overlap * 25.0)


def year_score(
    candidate: MovieDetails,
    year_min: int,
    year_max: int,
    liked: list[MovieDetails],
) -> float:
    if candidate.year is None:
        return 0.0
    if candidate.year < year_min or candidate.year > year_max:
        return 0.0
    liked_years = [movie.year for movie in liked if movie.year is not None]
    if not liked_years:
        return 100.0
    avg_year = _avg([float(year) for year in liked_years])
    distance = abs(candidate.year - avg_year)
    range_span = max(year_max - year_min, 1)
    proximity = max(0.0, 1.0 - (distance / range_span))
    return 60.0 + proximity * 40.0


def rating_score(candidate: MovieDetails, liked: list[MovieDetails]) -> float:
    if candidate.rating is None:
        return 0.0
    liked_ratings = [movie.rating for movie in liked if movie.rating is not None]
    if not liked_ratings:
        return min(100.0, candidate.rating * 10)
    avg_rating = _avg(liked_ratings)
    distance = abs(candidate.rating - avg_rating)
    return max(0.0, 100.0 - distance * 15.0)


def keyword_score(candidate: MovieDetails, liked: list[MovieDetails]) -> float:
    if not liked:
        return 0.0
    liked_keywords: set[str] = set()
    for movie in liked:
        liked_keywords.update(keyword.lower() for keyword in movie.keywords)
    candidate_keywords = {keyword.lower() for keyword in candidate.keywords}
    return _overlap_score(candidate_keywords, liked_keywords)


def composite_score(
    candidate: MovieDetails,
    liked: list[MovieDetails],
    disliked: list[MovieDetails],
    year_min: int,
    year_max: int,
    weights: MovieRecommenderWeights,
) -> ScoreBreakdown:
    breakdown = ScoreBreakdown(
        genre=genre_score(candidate, liked, disliked),
        cast_director=cast_director_score(candidate, liked),
        year=year_score(candidate, year_min, year_max, liked),
        rating=rating_score(candidate, liked),
        keywords=keyword_score(candidate, liked),
        total=0.0,
    )
    breakdown.total = round(
        breakdown.genre * weights.genre
        + breakdown.cast_director * weights.cast_director
        + breakdown.year * weights.year
        + breakdown.rating * weights.rating
        + breakdown.keywords * weights.keywords,
        1,
    )
    return breakdown
