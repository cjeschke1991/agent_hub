from __future__ import annotations

import base64
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, TypeVar

from agent_hub.core.config import HubConfig, load_config

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_PARALLEL_WORKERS = 8
EMBED_PARALLEL_WORKERS = 2
EMBED_MIN_REQUEST_INTERVAL = 0.45

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


class SpotifyError(RuntimeError):
    pass


class SpotifyConfigError(SpotifyError):
    pass


class SpotifyWebApiUnavailableError(SpotifyError):
    """Raised when Spotify Web API data endpoints are blocked (e.g. Premium required)."""


WEB_API_UNAVAILABLE_MESSAGE = (
    "Spotify text search is unavailable for this developer account "
    "(Premium subscription required). Paste a Spotify track or artist link/ID instead."
)


@dataclass
class TrackSearchResult:
    spotify_id: str
    title: str
    artist: str
    artist_id: str
    album: str
    year: int | None
    popularity: int
    image_url: str | None
    preview_url: str | None


@dataclass
class ArtistSearchResult:
    spotify_id: str
    name: str
    genres: list[str]
    popularity: int
    followers: int
    image_url: str | None


@dataclass
class TrackDetails:
    spotify_id: str
    title: str
    artist: str
    artist_id: str
    album: str
    year: int | None
    genres: list[str]
    energy: float | None
    valence: float | None
    danceability: float | None
    tempo: float | None
    popularity: int
    duration_ms: int | None
    image_url: str | None
    preview_url: str | None
    source_rank: int | None = None

    def audio_features_display(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if self.energy is not None:
            result["Energy"] = f"{self.energy:.0%}"
        if self.valence is not None:
            result["Mood"] = f"{self.valence:.0%} happy"
        if self.danceability is not None:
            result["Danceability"] = f"{self.danceability:.0%}"
        if self.tempo is not None:
            result["Tempo"] = f"{self.tempo:.0f} BPM"
        return result


@dataclass
class ArtistDetails:
    spotify_id: str
    name: str
    genres: list[str]
    popularity: int
    followers: int
    image_url: str | None


_token_cache: dict[str, object] = {"token": "", "expires_at": 0.0}
_genre_lookup_cache: dict[str, list[str]] = {}
_embed_page_cache: dict[str, dict] = {}
_embed_lock = threading.Lock()
_embed_last_request_at = 0.0


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionResetError, ConnectionAbortedError)):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, BaseException):
            return _is_transient_network_error(reason)
        text = str(reason).lower()
        return any(
            token in text
            for token in (
                "connection reset",
                "timed out",
                "connection refused",
                "broken pipe",
                "network is unreachable",
            )
        )
    if isinstance(exc, OSError):
        return exc.errno in {54, 61, 104, 110, 10054}
    return False


def _network_retry_delay(attempt: int) -> float:
    return float((2**attempt) + 1)


def map_parallel(
    items: list[T],
    fn: Callable[[T], R],
    *,
    max_workers: int = DEFAULT_PARALLEL_WORKERS,
) -> list[R | None]:
    """Run *fn* over *items* concurrently, preserving order. Failed items become None."""
    if not items:
        return []
    if len(items) == 1:
        try:
            return [fn(items[0])]
        except Exception:
            return [None]

    workers = min(max_workers, len(items))
    results: list[R | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {executor.submit(fn, item): idx for idx, item in enumerate(items)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = None
    return results


def _client_credentials(config: HubConfig | None = None) -> tuple[str, str]:
    config = config or load_config()
    client_id = config.spotify.client_id.strip()
    client_secret = config.spotify.client_secret.strip()
    if not client_id or not client_secret:
        raise SpotifyConfigError(
            "Spotify credentials not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
            "in your environment or config.yaml. "
            "Create a free app at https://developer.spotify.com/dashboard"
        )
    return client_id, client_secret


def _get_token(config: HubConfig | None = None) -> str:
    now = time.time()
    if _token_cache["token"] and float(_token_cache["expires_at"]) > now + 60:  # type: ignore[arg-type]
        return str(_token_cache["token"])
    client_id, client_secret = _client_credentials(config)
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    request = urllib.request.Request(
        SPOTIFY_TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SpotifyConfigError(f"Spotify auth failed ({exc.code}): {body}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SpotifyError(f"Could not reach Spotify: {exc}") from exc
    token = str(payload["access_token"])
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + int(payload.get("expires_in", 3600))
    return token


def _invalidate_token() -> None:
    _token_cache["expires_at"] = 0.0


def _request(path: str, params: dict | None = None, config: HubConfig | None = None) -> dict:
    token = _get_token(config)
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"{SPOTIFY_API_BASE}{path}{query}"
    max_attempts = 3
    last_error: BaseException | None = None
    for attempt in range(max_attempts):
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                _invalidate_token()
                raise SpotifyConfigError("Spotify rejected the access token. Check credentials.") from exc
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 403:
                lower = body.lower()
                if "premium" in lower or "subscription" in lower:
                    global _web_api_available
                    _web_api_available = False
            raise SpotifyError(f"Spotify request failed ({exc.code}): {body}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if _is_transient_network_error(exc) and attempt < max_attempts - 1:
                time.sleep(_network_retry_delay(attempt))
                continue
            raise SpotifyError(f"Could not reach Spotify: {exc}") from exc
    raise SpotifyError(f"Could not reach Spotify: {last_error}")


def spotify_configured(config: HubConfig | None = None) -> bool:
    config = config or load_config()
    return bool(config.spotify.client_id.strip() and config.spotify.client_secret.strip())


def is_spotify_catalog_id(spotify_id: str) -> bool:
    """True for real Spotify track/artist IDs (not synthetic pandora-* IDs)."""
    return bool(spotify_id) and not spotify_id.startswith("pandora-")


_web_api_available: bool | None = None


def spotify_web_api_available(config: HubConfig | None = None, *, force_check: bool = False) -> bool:
    """Whether authenticated Spotify Web API data endpoints respond (not 403-blocked)."""
    global _web_api_available
    if _web_api_available is not None and not force_check:
        return _web_api_available
    if not spotify_configured(config):
        _web_api_available = False
        return False
    try:
        _request("/search", {"q": "a", "type": "track", "limit": 1}, config=config)
        _web_api_available = True
    except SpotifyError as exc:
        message = str(exc).lower()
        if "403" in message or "premium" in message:
            _web_api_available = False
        else:
            _web_api_available = True
    return _web_api_available


def reset_spotify_web_api_cache() -> None:
    global _web_api_available
    _web_api_available = None


def _parse_image_url(images: list[dict]) -> str | None:
    if not images:
        return None
    url = images[0].get("url")
    return str(url) if url else None


def _year_from_date(value: str | None) -> int | None:
    if not value or len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def parse_track_id(value: str) -> str | None:
    value = value.strip()
    if "open.spotify.com/track/" in value:
        tail = value.split("open.spotify.com/track/", 1)[1]
        return tail.split("?", 1)[0].split("/", 1)[0]
    if value.startswith("spotify:track:"):
        return value.split(":", 2)[2]
    if re.fullmatch(r"[A-Za-z0-9]{22}", value):
        return value
    return None


def parse_artist_id(value: str) -> str | None:
    value = value.strip()
    if "open.spotify.com/artist/" in value:
        tail = value.split("open.spotify.com/artist/", 1)[1]
        return tail.split("?", 1)[0].split("/", 1)[0]
    if value.startswith("spotify:artist:"):
        return value.split(":", 2)[2]
    if re.fullmatch(r"[A-Za-z0-9]{22}", value):
        return value
    return None


def _track_details_to_search_result(details: TrackDetails) -> TrackSearchResult:
    return TrackSearchResult(
        spotify_id=details.spotify_id,
        title=details.title,
        artist=details.artist,
        artist_id=details.artist_id,
        album=details.album,
        year=details.year,
        popularity=details.popularity,
        image_url=details.image_url,
        preview_url=details.preview_url,
    )


def _artist_details_to_search_result(details: ArtistDetails) -> ArtistSearchResult:
    return ArtistSearchResult(
        spotify_id=details.spotify_id,
        name=details.name,
        genres=list(details.genres),
        popularity=details.popularity,
        followers=details.followers,
        image_url=details.image_url,
    )


def _search_tracks_by_spotify_reference(
    query: str,
    config: HubConfig | None = None,
) -> list[TrackSearchResult] | None:
    track_id = parse_track_id(query)
    if not track_id:
        return None
    details = get_track_details_with_fallback(track_id, config=config)
    return [_track_details_to_search_result(details)]


def _search_artists_by_spotify_reference(
    query: str,
    config: HubConfig | None = None,
) -> list[ArtistSearchResult] | None:
    artist_id = parse_artist_id(query)
    if not artist_id:
        return None
    details = get_artist_details_with_fallback(artist_id, config=config)
    return [_artist_details_to_search_result(details)]


def search_tracks(query: str, limit: int = 20, config: HubConfig | None = None) -> list[TrackSearchResult]:
    query = query.strip()
    if not query:
        return []
    reference_results = _search_tracks_by_spotify_reference(query, config=config)
    if reference_results is not None:
        return reference_results
    if not spotify_web_api_available(config):
        raise SpotifyWebApiUnavailableError(WEB_API_UNAVAILABLE_MESSAGE)
    payload = _request("/search", {"q": query, "type": "track", "limit": min(limit, 50)}, config=config)
    results: list[TrackSearchResult] = []
    for item in payload.get("tracks", {}).get("items", []):
        if not item.get("id"):
            continue
        album = item.get("album") or {}
        artists = item.get("artists") or []
        results.append(
            TrackSearchResult(
                spotify_id=str(item["id"]),
                title=str(item.get("name") or "Unknown"),
                artist=str(artists[0]["name"] if artists else "Unknown"),
                artist_id=str(artists[0]["id"] if artists else ""),
                album=str(album.get("name") or ""),
                year=_year_from_date(album.get("release_date")),
                popularity=int(item.get("popularity") or 0),
                image_url=_parse_image_url(album.get("images") or []),
                preview_url=item.get("preview_url"),
            )
        )
    return results


def search_artists(query: str, limit: int = 20, config: HubConfig | None = None) -> list[ArtistSearchResult]:
    query = query.strip()
    if not query:
        return []
    reference_results = _search_artists_by_spotify_reference(query, config=config)
    if reference_results is not None:
        return reference_results
    if not spotify_web_api_available(config):
        raise SpotifyWebApiUnavailableError(WEB_API_UNAVAILABLE_MESSAGE)
    payload = _request("/search", {"q": query, "type": "artist", "limit": min(limit, 50)}, config=config)
    results: list[ArtistSearchResult] = []
    for item in payload.get("artists", {}).get("items", []):
        if not item.get("id"):
            continue
        results.append(
            ArtistSearchResult(
                spotify_id=str(item["id"]),
                name=str(item.get("name") or "Unknown"),
                genres=list(item.get("genres") or []),
                popularity=int(item.get("popularity") or 0),
                followers=int((item.get("followers") or {}).get("total") or 0),
                image_url=_parse_image_url(item.get("images") or []),
            )
        )
    return results


def _fetch_audio_features(spotify_id: str, config: HubConfig | None = None) -> dict:
    try:
        return _request(f"/audio-features/{spotify_id}", config=config)
    except SpotifyError:
        return {}


def get_track_details(spotify_id: str, config: HubConfig | None = None) -> TrackDetails:
    track = _request(f"/tracks/{spotify_id}", config=config)
    album = track.get("album") or {}
    artists = track.get("artists") or []
    artist_id = str(artists[0]["id"]) if artists else ""
    genres: list[str] = []
    if artist_id:
        try:
            artist_data = _request(f"/artists/{artist_id}", config=config)
            genres = list(artist_data.get("genres") or [])
        except SpotifyError:
            pass
    features = _fetch_audio_features(spotify_id, config=config)
    return TrackDetails(
        spotify_id=str(track["id"]),
        title=str(track.get("name") or "Unknown"),
        artist=str(artists[0]["name"] if artists else "Unknown"),
        artist_id=artist_id,
        album=str(album.get("name") or ""),
        year=_year_from_date(album.get("release_date")),
        genres=genres,
        energy=float(features["energy"]) if features.get("energy") is not None else None,
        valence=float(features["valence"]) if features.get("valence") is not None else None,
        danceability=float(features["danceability"]) if features.get("danceability") is not None else None,
        tempo=float(features["tempo"]) if features.get("tempo") is not None else None,
        popularity=int(track.get("popularity") or 0),
        duration_ms=int(track.get("duration_ms") or 0) or None,
        image_url=_parse_image_url(album.get("images") or []),
        preview_url=track.get("preview_url"),
    )


def get_artist_details(spotify_id: str, config: HubConfig | None = None) -> ArtistDetails:
    data = _request(f"/artists/{spotify_id}", config=config)
    return ArtistDetails(
        spotify_id=str(data["id"]),
        name=str(data.get("name") or "Unknown"),
        genres=list(data.get("genres") or []),
        popularity=int(data.get("popularity") or 0),
        followers=int((data.get("followers") or {}).get("total") or 0),
        image_url=_parse_image_url(data.get("images") or []),
    )


def get_related_artist_ids(artist_id: str, config: HubConfig | None = None) -> list[str]:
    try:
        payload = _request(f"/artists/{artist_id}/related-artists", config=config)
        return [str(a["id"]) for a in payload.get("artists", []) if a.get("id")]
    except SpotifyError:
        return []


def get_artist_top_track_ids(
    artist_id: str, market: str = "US", config: HubConfig | None = None
) -> list[str]:
    try:
        payload = _request(f"/artists/{artist_id}/top-tracks", {"market": market}, config=config)
        return [str(t["id"]) for t in payload.get("tracks", []) if t.get("id")]
    except SpotifyError:
        return []


def get_spotify_recommendations(
    seed_track_ids: list[str] | None = None,
    seed_artist_ids: list[str] | None = None,
    seed_genres: list[str] | None = None,
    limit: int = 100,
    energy_min: float | None = None,
    energy_max: float | None = None,
    valence_min: float | None = None,
    valence_max: float | None = None,
    config: HubConfig | None = None,
) -> list[str]:
    """Return Spotify recommendation track IDs (max 5 seeds total).

    Note: Spotify removed this endpoint for apps created after Nov 2024.
    Returns empty list gracefully if unavailable.
    """
    seeds: dict[str, str] = {}
    track_seeds = (seed_track_ids or [])[:2]
    artist_seeds = (seed_artist_ids or [])[: max(1, 5 - len(track_seeds))]
    genre_seeds = (seed_genres or [])[:5]
    if track_seeds:
        seeds["seed_tracks"] = ",".join(track_seeds)
    if artist_seeds:
        seeds["seed_artists"] = ",".join(artist_seeds)
    if not seeds and genre_seeds:
        seeds["seed_genres"] = ",".join(genre_seeds)
    if not seeds:
        return []
    params: dict[str, object] = {"limit": min(limit, 100), **seeds}
    if energy_min is not None:
        params["min_energy"] = energy_min
    if energy_max is not None:
        params["max_energy"] = energy_max
    if valence_min is not None:
        params["min_valence"] = valence_min
    if valence_max is not None:
        params["max_valence"] = valence_max
    try:
        payload = _request("/recommendations", {str(k): str(v) for k, v in params.items()}, config=config)
        return [str(t["id"]) for t in payload.get("tracks", []) if t.get("id")]
    except SpotifyError:
        return []


def search_tracks_by_genre(genre: str, limit: int = 20, config: HubConfig | None = None) -> list[str]:
    try:
        payload = _request(
            "/search",
            {"q": f"genre:{genre}", "type": "track", "limit": min(limit, 50)},
            config=config,
        )
        return [
            str(item["id"])
            for item in payload.get("tracks", {}).get("items", [])
            if item.get("id")
        ]
    except SpotifyError:
        return []


# Standard Spotify recommendation genre seeds (used when the Web API is blocked).
SPOTIFY_FALLBACK_GENRE_SEEDS: tuple[str, ...] = (
    "acoustic",
    "afrobeat",
    "alt-rock",
    "alternative",
    "ambient",
    "blues",
    "bossanova",
    "brazil",
    "breakbeat",
    "british",
    "chicago-house",
    "children",
    "chill",
    "classical",
    "club",
    "comedy",
    "country",
    "dance",
    "dancehall",
    "deep-house",
    "detroit-techno",
    "disco",
    "drum-and-bass",
    "dub",
    "dubstep",
    "edm",
    "electro",
    "electronic",
    "emo",
    "folk",
    "funk",
    "garage",
    "gospel",
    "goth",
    "grunge",
    "guitar",
    "happy",
    "hard-rock",
    "hardcore",
    "hardstyle",
    "heavy-metal",
    "hip-hop",
    "honky-tonk",
    "house",
    "idm",
    "indie",
    "indie-pop",
    "industrial",
    "j-dance",
    "j-idol",
    "j-pop",
    "j-rock",
    "jazz",
    "k-pop",
    "kids",
    "latin",
    "latino",
    "malay",
    "mandopop",
    "metal",
    "metalcore",
    "minimal-techno",
    "new-age",
    "opera",
    "pagode",
    "party",
    "piano",
    "pop",
    "pop-film",
    "post-dubstep",
    "power-pop",
    "progressive-house",
    "psych-rock",
    "punk",
    "punk-rock",
    "r-n-b",
    "rainy-day",
    "reggae",
    "reggaeton",
    "rock",
    "rock-n-roll",
    "rockabilly",
    "romance",
    "sad",
    "salsa",
    "samba",
    "sertanejo",
    "show-tunes",
    "singer-songwriter",
    "ska",
    "sleep",
    "songwriter",
    "soul",
    "soundtracks",
    "spanish",
    "study",
    "summer",
    "swedish",
    "synth-pop",
    "tango",
    "techno",
    "trance",
    "trip-hop",
    "turkish",
    "work-out",
    "world-music",
)


def get_available_genre_seeds(config: HubConfig | None = None) -> list[str]:
    if not spotify_web_api_available(config):
        return list(SPOTIFY_FALLBACK_GENRE_SEEDS)
    try:
        payload = _request("/recommendations/available-genre-seeds", config=config)
        genres = list(payload.get("genres", []))
        if genres:
            return genres
    except SpotifyError:
        pass
    return list(SPOTIFY_FALLBACK_GENRE_SEEDS)


def parse_playlist_id(value: str) -> str:
    value = value.strip()
    if "open.spotify.com/playlist/" in value:
        tail = value.split("open.spotify.com/playlist/", 1)[1]
        return tail.split("?", 1)[0].split("/", 1)[0]
    if value.startswith("spotify:playlist:"):
        return value.split(":", 2)[2]
    return value


def _fetch_embed_next_data(embed_path: str) -> dict:
    path_key = embed_path.lstrip("/")
    cached = _embed_page_cache.get(path_key)
    if cached is not None:
        return cached

    embed_url = f"https://open.spotify.com/embed/{path_key}"
    headers = {"User-Agent": "Mozilla/5.0"}
    html = ""
    max_attempts = 4
    for attempt in range(max_attempts):
        with _embed_lock:
            global _embed_last_request_at
            wait = EMBED_MIN_REQUEST_INTERVAL - (time.time() - _embed_last_request_at)
            if wait > 0:
                time.sleep(wait)
            _embed_last_request_at = time.time()

        request = urllib.request.Request(embed_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < max_attempts - 1:
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else _network_retry_delay(attempt)
                time.sleep(delay)
                continue
            raise SpotifyError(
                f"Could not fetch Spotify embed page ({exc.code}): {exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if _is_transient_network_error(exc) and attempt < max_attempts - 1:
                time.sleep(_network_retry_delay(attempt))
                continue
            raise SpotifyError(f"Could not fetch Spotify embed page: {exc}") from exc
    else:
        raise SpotifyError("Could not fetch Spotify embed page after retries.")

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html,
    )
    if not match:
        raise SpotifyError("Could not parse Spotify embed page data.")
    payload = json.loads(match.group(1))
    _embed_page_cache[path_key] = payload
    return payload


def _track_details_from_embed_item(
    item: dict,
    *,
    artist_id: str = "",
    artist_name: str | None = None,
    source_rank: int | None = None,
) -> TrackDetails | None:
    uri = str(item.get("uri") or "")
    if not uri.startswith("spotify:track:"):
        return None
    spotify_id = uri.split(":", 2)[2]
    preview = item.get("audioPreview") or {}
    subtitle = str(item.get("subtitle") or artist_name or "Unknown")
    return TrackDetails(
        spotify_id=spotify_id,
        title=str(item.get("title") or "Unknown"),
        artist=subtitle,
        artist_id=artist_id,
        album="",
        year=_year_from_date(item.get("releaseDate")),
        genres=[],
        energy=None,
        valence=None,
        danceability=None,
        tempo=None,
        popularity=0,
        duration_ms=int(item["duration"]) if item.get("duration") else None,
        image_url=None,
        preview_url=preview.get("url"),
        source_rank=source_rank,
    )


def fetch_track_details_from_embed(track_id: str) -> TrackDetails:
    """Fetch track metadata from Spotify's public embed page."""
    payload = _fetch_embed_next_data(f"track/{track_id}")
    entity = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
    )
    artists = entity.get("artists") or []
    artist_id = ""
    artist_name = "Unknown"
    if artists:
        artist_name = str(artists[0].get("name") or "Unknown")
        artist_uri = str(artists[0].get("uri") or "")
        if artist_uri.startswith("spotify:artist:"):
            artist_id = artist_uri.split(":", 2)[2]
    details = _track_details_from_embed_item(
        entity,
        artist_id=artist_id,
        artist_name=artist_name,
    )
    if not details:
        raise SpotifyError(f"Could not parse track embed data for {track_id}.")
    return details


def fetch_artist_top_tracks_from_embed(
    artist_id: str,
    limit: int = 10,
) -> list[TrackDetails]:
    """Fetch an artist's top tracks from Spotify's public embed page."""
    payload = _fetch_embed_next_data(f"artist/{artist_id}")
    entity = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
    )
    track_list = entity.get("trackList") or []
    tracks: list[TrackDetails] = []
    for rank, item in enumerate(track_list[:limit]):
        details = _track_details_from_embed_item(
            item, artist_id=artist_id, source_rank=rank
        )
        if details:
            tracks.append(details)
    return tracks


def get_artist_top_tracks_with_fallback(
    artist_id: str,
    *,
    limit: int = 5,
    config: HubConfig | None = None,
) -> list[TrackDetails]:
    """Return an artist's top tracks, using embed pages when the Web API is unavailable."""
    if not is_spotify_catalog_id(artist_id):
        return []
    if spotify_web_api_available(config):
        track_ids = get_artist_top_track_ids(artist_id, config=config)
        tracks: list[TrackDetails] = []
        for rank, track_id in enumerate(track_ids[:limit]):
            try:
                track = get_track_details_with_fallback(track_id, config=config)
                track = TrackDetails(
                    spotify_id=track.spotify_id,
                    title=track.title,
                    artist=track.artist,
                    artist_id=track.artist_id,
                    album=track.album,
                    year=track.year,
                    genres=track.genres,
                    popularity=track.popularity,
                    energy=track.energy,
                    valence=track.valence,
                    danceability=track.danceability,
                    tempo=track.tempo,
                    duration_ms=track.duration_ms,
                    image_url=track.image_url,
                    preview_url=track.preview_url,
                    source_rank=rank,
                )
                tracks.append(track)
            except SpotifyError:
                continue
        if tracks:
            return tracks
    return fetch_artist_top_tracks_from_embed(artist_id, limit=limit)


def fetch_artist_details_from_embed(artist_id: str) -> ArtistDetails:
    """Fetch basic artist metadata from Spotify's public embed page."""
    payload = _fetch_embed_next_data(f"artist/{artist_id}")
    entity = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
    )
    images = (entity.get("visualIdentity") or {}).get("image") or []
    return ArtistDetails(
        spotify_id=str(entity.get("id") or artist_id),
        name=str(entity.get("name") or entity.get("title") or "Unknown"),
        genres=[],
        popularity=0,
        followers=0,
        image_url=_parse_image_url(images),
    )


def get_track_details_with_fallback(
    track_id: str,
    config: HubConfig | None = None,
) -> TrackDetails:
    if not is_spotify_catalog_id(track_id):
        raise SpotifyError(f"Not a Spotify track ID: {track_id}")
    if spotify_web_api_available(config):
        try:
            return get_track_details(track_id, config=config)
        except SpotifyError:
            pass
    return fetch_track_details_from_embed(track_id)


def get_artist_details_with_fallback(
    artist_id: str,
    config: HubConfig | None = None,
) -> ArtistDetails:
    if not is_spotify_catalog_id(artist_id):
        raise SpotifyError(f"Not a Spotify artist ID: {artist_id}")
    if spotify_web_api_available(config):
        try:
            return get_artist_details(artist_id, config=config)
        except SpotifyError:
            pass
    return fetch_artist_details_from_embed(artist_id)


_MUSICBRAINZ_USER_AGENT = "agent-hub/1.0 (music-recommender)"


def _clean_artist_genre_lookup_name(name: str) -> str:
    cleaned = re.sub(r"\s+explicit$", "", name, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.endswith("(Dance)"):
        cleaned = cleaned[: -len("(Dance)")].strip()
    return cleaned.replace("'", "ʻ") if "Kamakawiwo" in cleaned else cleaned.replace("'", "")


def fetch_artist_genres_from_musicbrainz(artist_name: str, *, limit: int = 8) -> list[str]:
    """Best-effort Spotify-style genre strings via MusicBrainz tags."""
    lookup_name = _clean_artist_genre_lookup_name(artist_name)
    if not lookup_name:
        return []

    quoted_name = f'"{lookup_name}"'
    search_url = (
        "https://musicbrainz.org/ws/2/artist/"
        f"?query=artist:{urllib.parse.quote(quoted_name)}&fmt=json&limit=5"
    )
    request = urllib.request.Request(search_url, headers={"User-Agent": _MUSICBRAINZ_USER_AGENT})
    try:
        payload = json.loads(urllib.request.urlopen(request, timeout=20).read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    artists = payload.get("artists") or []
    if not artists:
        return []

    target = lookup_name.lower().strip()
    if target.startswith("the "):
        target = target[4:]
    mbid = None
    for artist in artists:
        candidate = str(artist.get("name") or "").lower().strip()
        if candidate.startswith("the "):
            candidate = candidate[4:]
        if candidate == target:
            mbid = str(artist["id"])
            break
    if mbid is None:
        mbid = str(artists[0]["id"])

    time.sleep(1.1)
    detail_url = f"https://musicbrainz.org/ws/2/artist/{mbid}?inc=tags+genres&fmt=json"
    detail_request = urllib.request.Request(detail_url, headers={"User-Agent": _MUSICBRAINZ_USER_AGENT})
    try:
        detail = json.loads(urllib.request.urlopen(detail_request, timeout=20).read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    scored: dict[str, int] = {}
    for tag in detail.get("tags") or []:
        name = str(tag.get("name") or "").strip().lower()
        if name:
            scored[name] = max(scored.get(name, 0), int(tag.get("count") or 0))
    for genre in detail.get("genres") or []:
        name = str(genre.get("name") or "").strip().lower()
        if name:
            scored[name] = max(scored.get(name, 0), int(genre.get("count") or 0))

    ranked = sorted(scored.items(), key=lambda item: (-item[1], item[0]))
    return [name for name, _count in ranked[:limit]]


def get_artist_genres_with_fallback(
    artist_id: str,
    *,
    artist_name: str = "",
    config: HubConfig | None = None,
    limit: int = 8,
) -> list[str]:
    """Return Spotify artist genres, falling back to MusicBrainz tags when needed."""
    cache_key = f"{artist_id}|{artist_name.lower().strip()}"
    if cache_key in _genre_lookup_cache:
        return list(_genre_lookup_cache[cache_key])

    genres: list[str] = []
    if is_spotify_catalog_id(artist_id):
        if spotify_web_api_available(config):
            try:
                details = get_artist_details(artist_id, config=config)
                if details.genres:
                    genres = details.genres[:limit]
            except SpotifyError:
                pass
        if not genres:
            try:
                details = get_artist_details_with_fallback(artist_id, config=config)
                if details.genres:
                    genres = details.genres[:limit]
                artist_name = artist_name or details.name
            except SpotifyError:
                pass
    if not genres and artist_name:
        genres = fetch_artist_genres_from_musicbrainz(artist_name, limit=limit)

    _genre_lookup_cache[cache_key] = genres
    return genres


def collect_embed_recommendation_tracks(
    liked_songs: list,
    liked_artists: list,
    *,
    max_artists: int = 8,
    tracks_per_artist: int = 10,
) -> dict[str, TrackDetails]:
    """Discover candidate tracks via public embed pages (no Web API needed)."""
    results: dict[str, TrackDetails] = {}
    artist_ids: list[str] = []

    def add_artist_id(artist_id: str) -> None:
        if is_spotify_catalog_id(artist_id) and artist_id not in artist_ids:
            artist_ids.append(artist_id)

    for artist in liked_artists:
        if len(artist_ids) >= max_artists:
            break
        if artist.spotify_id and is_spotify_catalog_id(artist.spotify_id):
            add_artist_id(artist.spotify_id)

    songs_needing_embed: list[str] = []
    for song in liked_songs:
        if not is_spotify_catalog_id(song.spotify_id):
            continue
        if song.artist_id and is_spotify_catalog_id(song.artist_id):
            add_artist_id(song.artist_id)
            continue
        songs_needing_embed.append(song.spotify_id)

    # Cap per-track embed lookups — liked artists already supply most seed IDs.
    songs_needing_embed = songs_needing_embed[:10]

    def _embed_track_artist_id(track_id: str) -> str | None:
        try:
            details = fetch_track_details_from_embed(track_id)
        except SpotifyError:
            return None
        return details.artist_id or None

    for artist_id in map_parallel(
        songs_needing_embed,
        _embed_track_artist_id,
        max_workers=EMBED_PARALLEL_WORKERS,
    ):
        if artist_id:
            add_artist_id(artist_id)

    def _artist_top_tracks(artist_id: str) -> list[TrackDetails]:
        try:
            return fetch_artist_top_tracks_from_embed(artist_id, limit=tracks_per_artist)
        except SpotifyError:
            return []

    fetch_ids = artist_ids[:max_artists]
    for tracks in map_parallel(
        fetch_ids,
        _artist_top_tracks,
        max_workers=EMBED_PARALLEL_WORKERS,
    ):
        if not tracks:
            continue
        for track in tracks:
            results[track.spotify_id] = track
    return results


def prefetch_track_details(
    track_ids: list[str],
    *,
    existing: dict[str, TrackDetails] | None = None,
    config: HubConfig | None = None,
    max_workers: int = DEFAULT_PARALLEL_WORKERS,
) -> dict[str, TrackDetails]:
    """Fetch track metadata for IDs not already present in *existing*."""
    cache: dict[str, TrackDetails] = dict(existing or {})
    missing = [
        track_id
        for track_id in track_ids
        if track_id not in cache and is_spotify_catalog_id(track_id)
    ]
    if not missing:
        return cache

    def _fetch_one(track_id: str) -> TrackDetails | None:
        try:
            return get_track_details_with_fallback(track_id, config=config)
        except SpotifyError:
            return None

    for track_id, track in zip(missing, map_parallel(missing, _fetch_one, max_workers=max_workers)):
        if track is not None:
            cache[track_id] = track
    return cache


def collect_embed_candidate_artists(
    embed_track_cache: dict[str, "TrackDetails"],
    excluded_ids: set[str] | None = None,
) -> list[str]:
    """Return unique artist IDs found in embed_track_cache, excluding given IDs.

    The cache contains top tracks fetched from liked-artist pages, so an artist
    that appears across many tracks is strongly associated with the user's taste.
    """
    seen: set[str] = set(excluded_ids or set())
    result: list[str] = []
    for track in embed_track_cache.values():
        if (
            track.artist_id
            and is_spotify_catalog_id(track.artist_id)
            and track.artist_id not in seen
        ):
            seen.add(track.artist_id)
            result.append(track.artist_id)
    return result


_COLLAB_TEXT_RE = re.compile(
    r",|\s&\s|\bfeat\.?\b|\bfeaturing\b|\bwith\b",
    re.IGNORECASE,
)


def artist_text_suggests_collaboration(text: str) -> bool:
    return bool(_COLLAB_TEXT_RE.search(text))


def _artist_ids_from_embed_entity(entity: dict) -> list[str]:
    ids: list[str] = []
    for artist in entity.get("artists") or []:
        uri = str(artist.get("uri") or "")
        if uri.startswith("spotify:artist:"):
            artist_id = uri.split(":", 2)[2]
            if is_spotify_catalog_id(artist_id) and artist_id not in ids:
                ids.append(artist_id)
    return ids


def fetch_track_artist_ids_from_embed(track_id: str) -> list[str]:
    """Return every artist ID credited on a track's public embed page."""
    track_id = track_id.strip()
    if not is_spotify_catalog_id(track_id):
        return []
    payload = _fetch_embed_next_data(f"track/{track_id}")
    entity = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
    )
    return _artist_ids_from_embed_entity(entity)


def collect_collaborator_artist_candidates(
    liked_songs: list,
    embed_track_cache: dict[str, TrackDetails],
    seed_artist_ids: set[str],
    *,
    max_liked_track_lookups: int = 50,
) -> dict[str, int]:
    """Discover collaborator artist IDs and how often they appear on liked tracks.

    Spotify's public embed pages list every credited artist on a track. When the
    Web API related-artists endpoint is unavailable, collaborators on the user's
    liked songs and top-track cache are the best discovery signal available.

    Returns a map of artist ID -> number of tracks that artist is credited on.
    """
    seeds = {aid for aid in seed_artist_ids if is_spotify_catalog_id(aid)}
    counts: dict[str, int] = {}
    processed_tracks: set[str] = set()

    def add_collaborators(track_id: str) -> None:
        if not is_spotify_catalog_id(track_id) or track_id in processed_tracks:
            return
        processed_tracks.add(track_id)
        try:
            artist_ids = fetch_track_artist_ids_from_embed(track_id)
        except SpotifyError:
            return
        for artist_id in artist_ids:
            if artist_id in seeds:
                continue
            counts[artist_id] = counts.get(artist_id, 0) + 1

    liked_lookups = 0
    for song in liked_songs:
        if not is_spotify_catalog_id(song.spotify_id):
            continue
        add_collaborators(song.spotify_id)
        liked_lookups += 1
        if liked_lookups >= max_liked_track_lookups:
            break

    for track_id, track in embed_track_cache.items():
        if artist_text_suggests_collaboration(track.artist):
            add_collaborators(track_id)

    return counts


def fetch_new_release_candidates(
    *,
    limit: int = 40,
) -> list[TrackDetails]:
    """Fetch recently-released tracks via Spotify's public new-releases embed page.

    Falls back gracefully to an empty list when the embed structure changes or the
    page is unavailable — the Wild Card zone is optional and should not break the
    whole recommendation flow.
    """
    results: list[TrackDetails] = []
    try:
        payload = _fetch_embed_next_data("section/0JQ5DAqbMKFEC4WFtoNRpw")
        sections = (
            payload.get("props", {})
            .get("pageProps", {})
            .get("state", {})
            .get("data", {})
            .get("content", {})
            .get("items", [])
        )
        for section in sections:
            inner_items = section.get("data", {}).get("content", {}).get("items", [])
            for item in inner_items:
                item_type = (item.get("data") or {}).get("__typename", "")
                if item_type == "Track":
                    track = _track_details_from_embed_item(item.get("data", {}))
                    if track:
                        track = TrackDetails(
                            spotify_id=track.spotify_id,
                            title=track.title,
                            artist=track.artist,
                            artist_id=track.artist_id,
                            album=track.album,
                            year=track.year,
                            genres=track.genres,
                            popularity=track.popularity,
                            energy=track.energy,
                            valence=track.valence,
                            danceability=track.danceability,
                            image_url=track.image_url,
                            preview_url=track.preview_url,
                            source_rank=len(results),
                        )
                        results.append(track)
                        if len(results) >= limit:
                            return results
                elif item_type in ("Album", "Playlist"):
                    album_id = (item.get("data") or {}).get("id") or (
                        (item.get("data") or {}).get("uri") or ""
                    ).split(":")[-1]
                    if not album_id or not is_spotify_catalog_id(album_id):
                        continue
                    try:
                        entity_key = "album" if item_type == "Album" else "playlist"
                        embed_tracks = fetch_artist_top_tracks_from_embed(album_id) if False else []
                        _ = embed_tracks
                        if item_type == "Playlist":
                            embed_tracks = fetch_playlist_tracks_from_embed(album_id)
                        elif item_type == "Album":
                            album_payload = _fetch_embed_next_data(f"album/{album_id}")
                            track_list = (
                                album_payload.get("props", {})
                                .get("pageProps", {})
                                .get("state", {})
                                .get("data", {})
                                .get("entity", {})
                                .get("trackList", [])
                            )
                            embed_tracks = [
                                t for item2 in track_list
                                if (t := _track_details_from_embed_item(item2)) is not None
                            ]
                        for t in embed_tracks[:3]:
                            t2 = TrackDetails(
                                spotify_id=t.spotify_id, title=t.title, artist=t.artist,
                                artist_id=t.artist_id, album=t.album, year=t.year,
                                genres=t.genres, popularity=t.popularity, energy=t.energy,
                                valence=t.valence, danceability=t.danceability,
                                image_url=t.image_url, preview_url=t.preview_url,
                                source_rank=len(results),
                            )
                            results.append(t2)
                            if len(results) >= limit:
                                return results
                    except SpotifyError:
                        continue
    except Exception:  # noqa: BLE001
        pass
    return results


def fetch_playlist_tracks_from_embed(
    playlist_id: str,
    config: HubConfig | None = None,
) -> list[TrackDetails]:
    """Fetch public playlist tracks via Spotify embed page (no Premium API needed)."""
    playlist_id = parse_playlist_id(playlist_id)
    payload = _fetch_embed_next_data(f"playlist/{playlist_id}")
    track_list = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
        .get("trackList", [])
    )
    if not track_list:
        raise SpotifyError("Playlist embed page did not contain any tracks.")

    tracks: list[TrackDetails] = []
    for item in track_list:
        details = _track_details_from_embed_item(item)
        if details:
            tracks.append(details)
    return tracks

