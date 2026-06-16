from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from agent_hub.core.config import HubConfig, load_config

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


class SpotifyError(RuntimeError):
    pass


class SpotifyConfigError(SpotifyError):
    pass


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
    except urllib.error.URLError as exc:
        raise SpotifyError(f"Could not reach Spotify: {exc.reason}") from exc
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
        raise SpotifyError(f"Spotify request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise SpotifyError(f"Could not reach Spotify: {exc.reason}") from exc


def spotify_configured(config: HubConfig | None = None) -> bool:
    config = config or load_config()
    return bool(config.spotify.client_id.strip() and config.spotify.client_secret.strip())


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


def search_tracks(query: str, limit: int = 20, config: HubConfig | None = None) -> list[TrackSearchResult]:
    query = query.strip()
    if not query:
        return []
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


def get_available_genre_seeds(config: HubConfig | None = None) -> list[str]:
    try:
        payload = _request("/recommendations/available-genre-seeds", config=config)
        return list(payload.get("genres", []))
    except SpotifyError:
        return []


def parse_playlist_id(value: str) -> str:
    value = value.strip()
    if "open.spotify.com/playlist/" in value:
        tail = value.split("open.spotify.com/playlist/", 1)[1]
        return tail.split("?", 1)[0].split("/", 1)[0]
    if value.startswith("spotify:playlist:"):
        return value.split(":", 2)[2]
    return value


def fetch_playlist_tracks_from_embed(
    playlist_id: str,
    config: HubConfig | None = None,
) -> list[TrackDetails]:
    """Fetch public playlist tracks via Spotify embed page (no Premium API needed)."""
    playlist_id = parse_playlist_id(playlist_id)
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    request = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SpotifyError(f"Could not fetch playlist embed page: {exc.reason}") from exc

    import re

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html,
    )
    if not match:
        raise SpotifyError("Could not parse playlist data from Spotify embed page.")

    payload = json.loads(match.group(1))
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
        uri = str(item.get("uri") or "")
        if not uri.startswith("spotify:track:"):
            continue
        spotify_id = uri.split(":", 2)[2]
        preview = item.get("audioPreview") or {}
        tracks.append(
            TrackDetails(
                spotify_id=spotify_id,
                title=str(item.get("title") or "Unknown"),
                artist=str(item.get("subtitle") or "Unknown"),
                artist_id="",
                album="",
                year=None,
                genres=[],
                energy=None,
                valence=None,
                danceability=None,
                tempo=None,
                popularity=0,
                duration_ms=int(item["duration"]) if item.get("duration") else None,
                image_url=None,
                preview_url=preview.get("url"),
            )
        )
    return tracks

