from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from agent_hub.agents.movie_recommender.explain import recommendation_reason
from agent_hub.agents.movie_recommender.omdb import fetch_omdb_details, omdb_configured
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
from agent_hub.core.api_cache import cache_get_pickle, cache_key, cache_set_pickle
from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.movie_db import connect, init_db
from agent_hub.core.parallel import map_parallel
from agent_hub.core.slices import utc_now_iso

_RECOMMEND_CACHE_TTL = 3600

KIDS_MOVIE_GENRES = frozenset({"Family", "Animation"})
KIDS_TMDB_GENRE_IDS = (10751, 16)


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
    imdb_id: str | None
    imdb_rating: str | None
    rotten_tomatoes_score: str | None
    metacritic_score: str | None
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
            imdb_id=self.imdb_id,
            imdb_rating=self.imdb_rating,
            rotten_tomatoes_score=self.rotten_tomatoes_score,
            metacritic_score=self.metacritic_score,
        )


@dataclass
class WishlistMovie:
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
    imdb_id: str | None
    imdb_rating: str | None
    rotten_tomatoes_score: str | None
    metacritic_score: str | None
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
            imdb_id=self.imdb_id,
            imdb_rating=self.imdb_rating,
            rotten_tomatoes_score=self.rotten_tomatoes_score,
            metacritic_score=self.metacritic_score,
        )


@dataclass
class Recommendation:
    movie: MovieDetails
    score: ScoreBreakdown
    reason: str


@dataclass
class RecommendFilters:
    year_min: int
    year_max: int
    genre_names: list[str]
    count: int = 10
    kids_only: bool = False


def is_kids_movie(details: MovieDetails) -> bool:
    return bool(set(details.genres) & KIDS_MOVIE_GENRES)


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
        imdb_id=row["imdb_id"],
        imdb_rating=row["imdb_rating"],
        rotten_tomatoes_score=row["rotten_tomatoes_score"],
        metacritic_score=row["metacritic_score"],
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
        "imdb_id": details.imdb_id,
        "imdb_rating": details.imdb_rating,
        "rotten_tomatoes_score": details.rotten_tomatoes_score,
        "metacritic_score": details.metacritic_score,
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
                    imdb_id = ?, imdb_rating = ?, rotten_tomatoes_score = ?, metacritic_score = ?,
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
                    fields["imdb_id"],
                    fields["imdb_rating"],
                    fields["rotten_tomatoes_score"],
                    fields["metacritic_score"],
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
                    rating, runtime, poster_url, overview, imdb_id, imdb_rating,
                    rotten_tomatoes_score, metacritic_score, sentiment, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    fields["imdb_id"],
                    fields["imdb_rating"],
                    fields["rotten_tomatoes_score"],
                    fields["metacritic_score"],
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


def _row_to_wishlist(row: Any) -> WishlistMovie:
    return WishlistMovie(
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
        imdb_id=row["imdb_id"],
        imdb_rating=row["imdb_rating"],
        rotten_tomatoes_score=row["rotten_tomatoes_score"],
        metacritic_score=row["metacritic_score"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _upsert_wishlist(details: MovieDetails, config: HubConfig | None = None) -> WishlistMovie:
    ensure_db(config)
    now = utc_now_iso()
    fields = _details_to_row_fields(details)
    with connect(config=config) as conn:
        existing = conn.execute(
            "SELECT id FROM wishlist_movies WHERE tmdb_id = ?",
            (details.tmdb_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE wishlist_movies
                SET title = ?, year = ?, genres = ?, director = ?, cast = ?, keywords = ?,
                    rating = ?, runtime = ?, poster_url = ?, overview = ?,
                    imdb_id = ?, imdb_rating = ?, rotten_tomatoes_score = ?, metacritic_score = ?,
                    updated_at = ?
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
                    fields["imdb_id"],
                    fields["imdb_rating"],
                    fields["rotten_tomatoes_score"],
                    fields["metacritic_score"],
                    now,
                    details.tmdb_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO wishlist_movies (
                    tmdb_id, title, year, genres, director, cast, keywords,
                    rating, runtime, poster_url, overview, imdb_id, imdb_rating,
                    rotten_tomatoes_score, metacritic_score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    fields["imdb_id"],
                    fields["imdb_rating"],
                    fields["rotten_tomatoes_score"],
                    fields["metacritic_score"],
                    now,
                    now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM wishlist_movies WHERE tmdb_id = ?",
            (details.tmdb_id,),
        ).fetchone()
    return _row_to_wishlist(row)


def add_to_wishlist(tmdb_id: int, config: HubConfig | None = None) -> WishlistMovie:
    details = get_movie_details(tmdb_id, config=config)
    return _upsert_wishlist(details, config=config)


def remove_from_wishlist(tmdb_id: int, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute("DELETE FROM wishlist_movies WHERE tmdb_id = ?", (tmdb_id,))


def list_wishlist(config: HubConfig | None = None) -> list[WishlistMovie]:
    ensure_db(config)
    with connect(config=config) as conn:
        rows = conn.execute(
            "SELECT * FROM wishlist_movies ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_wishlist(row) for row in rows]


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


def _enrich_with_omdb(details: MovieDetails, config: HubConfig) -> MovieDetails:
    if not omdb_configured(config) or not details.imdb_id:
        return details
    if details.rotten_tomatoes_score and details.metacritic_score and details.imdb_rating:
        return details
    omdb = fetch_omdb_details(details.imdb_id, config=config)
    if not omdb:
        return details
    return replace(
        details,
        rotten_tomatoes_score=details.rotten_tomatoes_score or omdb.rotten_tomatoes_score,
        metacritic_score=details.metacritic_score or omdb.metacritic_score,
        imdb_rating=details.imdb_rating or omdb.imdb_rating,
    )


def _taste_profile_details(movies: list[TasteMovie], config: HubConfig) -> list[MovieDetails]:
    return [_enrich_with_omdb(movie.to_details(), config) for movie in movies]


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

    if filters.kids_only and genre_ids:
        for page in (1, 2):
            for kids_genre_id in KIDS_TMDB_GENRE_IDS:
                combined = sorted({kids_genre_id, *genre_ids})
                add_ids(
                    discover_movie_ids(
                        filters.year_min,
                        filters.year_max,
                        genre_ids=combined,
                        page=page,
                        config=config,
                    )
                )
    elif filters.kids_only:
        for page in (1, 2):
            for kids_genre_id in KIDS_TMDB_GENRE_IDS:
                add_ids(
                    discover_movie_ids(
                        filters.year_min,
                        filters.year_max,
                        genre_ids=[kids_genre_id],
                        page=page,
                        config=config,
                    )
                )
    else:
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


def _recommend_cache_key(filters: RecommendFilters, liked: list[TasteMovie], disliked: list[TasteMovie]) -> str:
    return cache_key(
        filters.year_min,
        filters.year_max,
        sorted(filters.genre_names),
        filters.count,
        filters.kids_only,
        sorted(movie.tmdb_id for movie in liked),
        sorted(movie.tmdb_id for movie in disliked),
    )


def recommend(filters: RecommendFilters, config: HubConfig | None = None) -> list[Recommendation]:
    config = config or load_config()
    liked = list_liked(config)
    if not liked:
        raise RecommendationError("Add at least one liked movie before requesting recommendations.")

    if filters.year_min > filters.year_max:
        raise MovieValidationError("Year minimum cannot be greater than year maximum.")
    if filters.count < 1:
        raise MovieValidationError("Recommendation count must be at least 1.")

    disliked_movies = list_disliked(config)
    cache_id = _recommend_cache_key(filters, liked, disliked_movies)
    cached = cache_get_pickle(
        config.data_dir,
        "movie_recommendations",
        cache_id,
        ttl_seconds=_RECOMMEND_CACHE_TTL,
    )
    if cached is not None:
        return cached

    try:
        candidate_ids = _collect_candidate_ids(filters, liked, config)
    except TmdbConfigError:
        raise

    disliked = _taste_profile_details(disliked_movies, config)
    liked_details = _taste_profile_details(liked, config)
    weights = config.movie_recommender.weights

    def _score_candidate(tmdb_id: int) -> Recommendation | None:
        try:
            details = get_movie_details(tmdb_id, config=config)
        except Exception:
            return None
        if details.year is not None and (
            details.year < filters.year_min or details.year > filters.year_max
        ):
            return None
        if filters.genre_names and not set(details.genres) & set(filters.genre_names):
            return None
        if filters.kids_only and not is_kids_movie(details):
            return None
        score = composite_score(
            details,
            liked_details,
            disliked,
            filters.year_min,
            filters.year_max,
            weights,
        )
        reason = recommendation_reason(details, liked_details, disliked, score)
        return Recommendation(movie=details, score=score, reason=reason)

    recommendations = [
        rec for rec in map_parallel(candidate_ids, _score_candidate, max_workers=8) if rec
    ]
    recommendations.sort(key=lambda item: item.score.total, reverse=True)
    final = recommendations[: filters.count]
    cache_set_pickle(config.data_dir, "movie_recommendations", cache_id, final)
    return final
