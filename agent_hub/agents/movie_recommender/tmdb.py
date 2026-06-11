from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from agent_hub.core.config import HubConfig, load_config

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"


class TmdbError(RuntimeError):
    pass


class TmdbConfigError(TmdbError):
    pass


@dataclass
class Genre:
    id: int
    name: str


@dataclass
class MovieSearchResult:
    tmdb_id: int
    title: str
    year: int | None
    overview: str
    rating: float | None
    poster_url: str | None


@dataclass
class MovieDetails:
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


def _api_key(config: HubConfig | None = None) -> str:
    config = config or load_config()
    key = config.tmdb.api_key.strip()
    if not key:
        raise TmdbConfigError(
            "TMDB API key not configured. Set TMDB_API_KEY in your environment or "
            "add tmdb.api_key to config.yaml. Get a free key at https://www.themoviedb.org/settings/api"
        )
    return key


def _request(path: str, params: dict | None = None, config: HubConfig | None = None) -> dict:
    params = dict(params or {})
    params["api_key"] = _api_key(config)
    query = urllib.parse.urlencode(params)
    url = f"{TMDB_BASE_URL}{path}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise TmdbConfigError("TMDB rejected the API key. Check TMDB_API_KEY or config.yaml.") from exc
        body = exc.read().decode("utf-8", errors="replace")
        raise TmdbError(f"TMDB request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise TmdbError(f"Could not reach TMDB: {exc.reason}") from exc


def _poster_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE}{path}"


def _year_from_date(value: str | None) -> int | None:
    if not value or len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def _parse_movie_details(payload: dict) -> MovieDetails:
    credits = payload.get("credits") or {}
    keywords_block = payload.get("keywords") or {}
    directors = [
        person["name"]
        for person in credits.get("crew", [])
        if person.get("job") == "Director" and person.get("name")
    ]
    cast = [
        person["name"]
        for person in credits.get("cast", [])[:5]
        if person.get("name")
    ]
    keywords = [
        item["name"]
        for item in keywords_block.get("keywords", [])
        if item.get("name")
    ]
    genres = [genre["name"] for genre in payload.get("genres", []) if genre.get("name")]
    return MovieDetails(
        tmdb_id=int(payload["id"]),
        title=str(payload.get("title") or payload.get("name") or "Unknown"),
        year=_year_from_date(payload.get("release_date")),
        genres=genres,
        director=directors[0] if directors else None,
        cast=cast,
        keywords=keywords,
        rating=float(payload["vote_average"]) if payload.get("vote_average") is not None else None,
        runtime=int(payload["runtime"]) if payload.get("runtime") else None,
        poster_url=_poster_url(payload.get("poster_path")),
        overview=str(payload.get("overview") or ""),
    )


def search_movies(query: str, config: HubConfig | None = None) -> list[MovieSearchResult]:
    query = query.strip()
    if not query:
        return []
    payload = _request("/search/movie", {"query": query, "include_adult": "false"}, config=config)
    results: list[MovieSearchResult] = []
    for item in payload.get("results", []):
        if not item.get("id"):
            continue
        results.append(
            MovieSearchResult(
                tmdb_id=int(item["id"]),
                title=str(item.get("title") or "Unknown"),
                year=_year_from_date(item.get("release_date")),
                overview=str(item.get("overview") or ""),
                rating=float(item["vote_average"]) if item.get("vote_average") is not None else None,
                poster_url=_poster_url(item.get("poster_path")),
            )
        )
    return results


def get_movie_details(tmdb_id: int, config: HubConfig | None = None) -> MovieDetails:
    payload = _request(
        f"/movie/{tmdb_id}",
        {"append_to_response": "credits,keywords"},
        config=config,
    )
    return _parse_movie_details(payload)


def list_genres(config: HubConfig | None = None) -> list[Genre]:
    payload = _request("/genre/movie/list", config=config)
    return [
        Genre(id=int(item["id"]), name=str(item["name"]))
        for item in payload.get("genres", [])
        if item.get("id") and item.get("name")
    ]


def discover_movie_ids(
    year_min: int,
    year_max: int,
    genre_ids: list[int] | None = None,
    page: int = 1,
    config: HubConfig | None = None,
) -> list[int]:
    params: dict[str, str | int] = {
        "primary_release_date.gte": f"{year_min}-01-01",
        "primary_release_date.lte": f"{year_max}-12-31",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": page,
    }
    if genre_ids:
        params["with_genres"] = ",".join(str(genre_id) for genre_id in genre_ids)
    payload = _request("/discover/movie", params, config=config)
    return [int(item["id"]) for item in payload.get("results", []) if item.get("id")]


def get_similar_ids(tmdb_id: int, config: HubConfig | None = None) -> list[int]:
    payload = _request(f"/movie/{tmdb_id}/similar", config=config)
    return [int(item["id"]) for item in payload.get("results", []) if item.get("id")]


def get_recommendation_ids(tmdb_id: int, config: HubConfig | None = None) -> list[int]:
    payload = _request(f"/movie/{tmdb_id}/recommendations", config=config)
    return [int(item["id"]) for item in payload.get("results", []) if item.get("id")]
