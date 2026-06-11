from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agent_hub.agents.movie_recommender.scoring import ScoreBreakdown, composite_score
from agent_hub.agents.movie_recommender.tmdb import (
    MovieDetails,
    MovieSearchResult,
    TmdbConfigError,
    discover_movie_ids,
    get_movie_details,
    get_recommendation_ids,
    get_similar_ids,
    list_genres,
    search_movies,
)
from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.movie_db import connect, init_db
from agent_hub.core.slices import utc_now_iso


class MovieValidationError(ValueError):
    pass


class RecommendationError(RuntimeError):
    pass


@dataclass
class TasteMovie:
    id: int
    tmdb_id: int
    title: str
    year: int | None
    genres: list[str]
    director: str | None
    cast: list[str]
    keywords: list[str]
    rating: float | None
    runtime: int | None
    poster_url: str | None
    overview: str
    sentiment: str
    created_at: str
    updated_at: str

    def to_details(self) -> MovieDetails:
        return MovieDetails(
            tmdb_id=self.tmdb_id,
            title=self.title,
            year=self.year,
            genres=self.genres,
            director=self.director,
            cast=self.cast,
            keywords=self.keywords,
            rating=self.rating,
            runtime=self.runtime,
            poster_url=self.poster_url,
            overview=self.overview,
        )


@dataclass
class Recommendation:
    movie: MovieDetails
    score: ScoreBreakdown


@dataclass
class RecommendFilters:
    year_min: int
    year_max: int
    genre_names: list[str]
    count: int = 10


def ensure_db(config: HubConfig | None = None) -> None:
    init_db(config)


def tmdb_configured(config: HubConfig | None = None) -> bool:
    config = config or load_config()
    return bool(config.tmdb.api_key.strip())


def _json_list(value: list[str]) -> str:
    return json.dumps(value)


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def _row_to_taste(row: Any) -> TasteMovie:
    return TasteMovie(
        id=int(row["id"]),
        tmdb_id=int(row["tmdb_id"]),
        title=str(row["title"]),
        year=int(row["year"]) if row["year"] is not None else None,
        genres=_parse_json_list(row["genres"]),
        director=row["director"],
        cast=_parse_json_list(row["cast"]),
        keywords=_parse_json_list(row["keywords"]),
        rating=float(row["rating"]) if row["rating"] is not None else None,
        runtime=int(row["runtime"]) if row["runtime"] is not None else None,
        poster_url=row["poster_url"],
        overview=str(row["overview"] or ""),
        sentiment=str(row["sentiment"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _details_to_row_fields(details: MovieDetails) -> dict[str, Any]:
    return {
        "title": details.title,
        "year": details.year,
        "genres": _json_list(details.genres),
        "director": details.director,
        "cast": _json_list(details.cast),
        "keywords": _json_list(details.keywords),
        "rating": details.rating,
        "runtime": details.runtime,
        "poster_url": details.poster_url,
        "overview": details.overview,
    }


def _upsert_taste(details: MovieDetails, sentiment: str, config: HubConfig | None = None) -> TasteMovie:
    if sentiment not in {"like", "dislike"}:
        raise MovieValidationError("Sentiment must be 'like' or 'dislike'.")
    ensure_db(config)
    now = utc_now_iso()
    fields = _details_to_row_fields(details)
    with connect(config=config) as conn:
        existing = conn.execute(
            "SELECT id FROM taste_movies WHERE tmdb_id = ?",
            (details.tmdb_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE taste_movies
                SET title = ?, year = ?, genres = ?, director = ?, cast = ?, keywords = ?,
                    rating = ?, runtime = ?, poster_url = ?, overview = ?,
                    sentiment = ?, updated_at = ?
                WHERE tmdb_id = ?
                """,
                (
                    fields["title"],
                    fields["year"],
                    fields["genres"],
                    fields["director"],
                    fields["cast"],
                    fields["keywords"],
                    fields["rating"],
                    fields["runtime"],
                    fields["poster_url"],
                    fields["overview"],
                    sentiment,
                    now,
                    details.tmdb_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO taste_movies (
                    tmdb_id, title, year, genres, director, cast, keywords,
                    rating, runtime, poster_url, overview, sentiment, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    details.tmdb_id,
                    fields["title"],
                    fields["year"],
                    fields["genres"],
                    fields["director"],
                    fields["cast"],
                    fields["keywords"],
                    fields["rating"],
                    fields["runtime"],
                    fields["poster_url"],
                    fields["overview"],
                    sentiment,
                    now,
                    now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM taste_movies WHERE tmdb_id = ?",
            (details.tmdb_id,),
        ).fetchone()
    return _row_to_taste(row)


def add_movie(tmdb_id: int, sentiment: str, config: HubConfig | None = None) -> TasteMovie:
    details = get_movie_details(tmdb_id, config=config)
    return _upsert_taste(details, sentiment, config=config)


def remove_movie(tmdb_id: int, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute("DELETE FROM taste_movies WHERE tmdb_id = ?", (tmdb_id,))


def list_taste_movies(sentiment: str | None = None, config: HubConfig | None = None) -> list[TasteMovie]:
    ensure_db(config)
    with connect(config=config) as conn:
        if sentiment:
            rows = conn.execute(
                "SELECT * FROM taste_movies WHERE sentiment = ? ORDER BY title COLLATE NOCASE",
                (sentiment,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM taste_movies ORDER BY sentiment, title COLLATE NOCASE").fetchall()
    return [_row_to_taste(row) for row in rows]


def list_liked(config: HubConfig | None = None) -> list[TasteMovie]:
    return list_taste_movies("like", config=config)


def list_disliked(config: HubConfig | None = None) -> list[TasteMovie]:
    return list_taste_movies("dislike", config=config)


def get_tmdb_genres(config: HubConfig | None = None) -> list[dict[str, Any]]:
    return [{"id": genre.id, "name": genre.name} for genre in list_genres(config=config)]


def search_tmdb(query: str, config: HubConfig | None = None) -> list[MovieSearchResult]:
    return search_movies(query, config=config)


def _genre_name_to_ids(genre_names: list[str], config: HubConfig | None = None) -> list[int]:
    if not genre_names:
        return []
    lookup = {genre.name.lower(): genre.id for genre in list_genres(config=config)}
    ids: list[int] = []
    for name in genre_names:
        genre_id = lookup.get(name.lower())
        if genre_id is not None:
            ids.append(genre_id)
    return ids


def _collect_candidate_ids(filters: RecommendFilters, liked: list[TasteMovie], config: HubConfig | None) -> list[int]:
    excluded = {movie.tmdb_id for movie in liked}
    excluded.update(movie.tmdb_id for movie in list_disliked(config))
    genre_ids = _genre_name_to_ids(filters.genre_names, config=config)

    candidate_ids: list[int] = []
    seen: set[int] = set()

    def add_ids(ids: list[int]) -> None:
        for tmdb_id in ids:
            if tmdb_id in excluded or tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            candidate_ids.append(tmdb_id)

    for page in (1, 2):
        add_ids(
            discover_movie_ids(
                filters.year_min,
                filters.year_max,
                genre_ids=genre_ids or None,
                page=page,
                config=config,
            )
        )

    for liked_movie in liked:
        add_ids(get_similar_ids(liked_movie.tmdb_id, config=config))
        add_ids(get_recommendation_ids(liked_movie.tmdb_id, config=config))

    return candidate_ids


def recommend(filters: RecommendFilters, config: HubConfig | None = None) -> list[Recommendation]:
    config = config or load_config()
    liked = list_liked(config)
    if not liked:
        raise RecommendationError("Add at least one liked movie before requesting recommendations.")

    if filters.year_min > filters.year_max:
        raise MovieValidationError("Year minimum cannot be greater than year maximum.")
    if filters.count < 1:
        raise MovieValidationError("Recommendation count must be at least 1.")

    try:
        candidate_ids = _collect_candidate_ids(filters, liked, config)
    except TmdbConfigError:
        raise

    disliked = [movie.to_details() for movie in list_disliked(config)]
    liked_details = [movie.to_details() for movie in liked]
    weights = config.movie_recommender.weights

    recommendations: list[Recommendation] = []
    for tmdb_id in candidate_ids:
        try:
            details = get_movie_details(tmdb_id, config=config)
        except Exception:
            continue
        if details.year is not None and (details.year < filters.year_min or details.year > filters.year_max):
            continue
        if filters.genre_names and not set(details.genres) & {name for name in filters.genre_names}:
            continue
        score = composite_score(
            details,
            liked_details,
            disliked,
            filters.year_min,
            filters.year_max,
            weights,
        )
        recommendations.append(Recommendation(movie=details, score=score))

    recommendations.sort(key=lambda item: item.score.total, reverse=True)
    return recommendations[: filters.count]
