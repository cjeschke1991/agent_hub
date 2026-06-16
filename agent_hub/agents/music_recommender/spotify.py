from __future__ import annotations

import base64
import json
import re
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


def _fetch_embed_next_data(embed_path: str) -> dict:
    embed_url = f"https://open.spotify.com/embed/{embed_path.lstrip('/')}"
    request = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SpotifyError(f"Could not fetch Spotify embed page: {exc.reason}") from exc

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html,
    )
    if not match:
        raise SpotifyError("Could not parse Spotify embed page data.")
    return json.loads(match.group(1))


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

    for artist in liked_artists[:max_artists]:
        add_artist_id(artist.spotify_id)

    for song in liked_songs:
        if not is_spotify_catalog_id(song.spotify_id):
            continue
        if song.artist_id:
            add_artist_id(song.artist_id)
            continue
        try:
            details = fetch_track_details_from_embed(song.spotify_id)
        except SpotifyError:
            continue
        if details.artist_id:
            add_artist_id(details.artist_id)

    for artist_id in artist_ids[:max_artists]:
        try:
            for track in fetch_artist_top_tracks_from_embed(
                artist_id, limit=tracks_per_artist
            ):
                results[track.spotify_id] = track
        except SpotifyError:
            continue
    return results


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

