from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agent_hub.agents.music_recommender.pandora import (
    fetch_pandora_playlist_tracks,
    parse_tracks_from_accessibility_snapshot,
    track_details_from_pandora,
)
from agent_hub.agents.music_recommender.explain import artist_reason, song_reason
from agent_hub.agents.music_recommender.scoring import (
    ArtistScoreBreakdown,
    SongScoreBreakdown,
    artist_score,
    artist_taste_text_match,
    song_score,
    taste_text_similarity,
)
from agent_hub.agents.music_recommender.spotify import (
    ArtistDetails,
    SpotifyConfigError,
    SpotifyError,
    TrackDetails,
    collect_collaborator_artist_candidates,
    collect_embed_candidate_artists,
    collect_embed_recommendation_tracks,
    fetch_artist_top_tracks_from_embed,
    fetch_new_release_candidates,
    fetch_playlist_tracks_from_embed,
    fetch_track_artist_ids_from_embed,
    fetch_track_details_from_embed,
    get_available_genre_seeds,
    get_artist_genres_with_fallback,
    get_artist_details,
    get_artist_details_with_fallback,
    get_artist_top_tracks_with_fallback,
    get_artist_top_track_ids,
    get_related_artist_ids,
    get_spotify_recommendations,
    get_track_details,
    get_track_details_with_fallback,
    is_spotify_catalog_id,
    map_parallel,
    EMBED_PARALLEL_WORKERS,
    search_artists,
    search_tracks,
    search_tracks_by_genre,
    spotify_configured,
    spotify_web_api_available,
)
from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.music_db import connect, init_db, pandora_artist_id
from agent_hub.core.slices import utc_now_iso


class MusicValidationError(ValueError):
    pass


class MusicRecommendationError(RuntimeError):
    pass


def ensure_db(config: HubConfig | None = None) -> None:
    init_db(config)


def _parse_json_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    try:
        parsed = json.loads(str(value))
        return [str(v) for v in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _json_dumps(lst: list[str]) -> str:
    return json.dumps(lst)


@dataclass
class TasteSong:
    id: int
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
    sentiment: str
    created_at: str
    updated_at: str


@dataclass
class TasteArtist:
    id: int
    pandora_id: str
    spotify_id: str | None
    name: str
    genres: list[str]
    popularity: int
    followers: int
    image_url: str | None
    sentiment: str
    created_at: str
    updated_at: str


@dataclass
class ArtistTopTrack:
    rank: int
    spotify_id: str
    title: str
    artist: str
    album: str
    year: int | None
    image_url: str | None
    preview_url: str | None


@dataclass
class WishlistSong:
    id: int
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
    created_at: str
    updated_at: str


@dataclass
class WishlistArtist:
    id: int
    spotify_id: str
    name: str
    genres: list[str]
    popularity: int
    followers: int
    image_url: str | None
    created_at: str
    updated_at: str


@dataclass
class SongRecommendation:
    track: TrackDetails
    score: SongScoreBreakdown
    reason: str
    zone: str = "safe"  # "safe" | "stretch" | "wild_card"


@dataclass
class ArtistRecommendation:
    artist: ArtistDetails
    related_liked_count: int
    score: ArtistScoreBreakdown
    reason: str


@dataclass
class MusicRecommendFilters:
    year_min: int = 1980
    year_max: int = 2026
    genre_names: list[str] | None = None
    song_count: int = 10
    artist_count: int = 10
    energy_min: float = 0.0
    energy_max: float = 1.0
    valence_min: float = 0.0
    valence_max: float = 1.0
    include_energy: bool = True
    include_valence: bool = True
    include_year: bool = True


def _row_to_taste_song(row: Any) -> TasteSong:
    return TasteSong(
        id=int(row["id"]),
        spotify_id=str(row["spotify_id"]),
        title=str(row["title"]),
        artist=str(row["artist"]),
        artist_id=str(row["artist_id"] or ""),
        album=str(row["album"] or ""),
        year=int(row["year"]) if row["year"] is not None else None,
        genres=_parse_json_list(row["genres"]),
        energy=float(row["energy"]) if row["energy"] is not None else None,
        valence=float(row["valence"]) if row["valence"] is not None else None,
        danceability=float(row["danceability"]) if row["danceability"] is not None else None,
        tempo=float(row["tempo"]) if row["tempo"] is not None else None,
        popularity=int(row["popularity"] or 0),
        duration_ms=int(row["duration_ms"]) if row["duration_ms"] is not None else None,
        image_url=row["image_url"],
        preview_url=row["preview_url"],
        sentiment=str(row["sentiment"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_taste_artist(row: Any) -> TasteArtist:
    spotify_id = row["spotify_id"]
    return TasteArtist(
        id=int(row["id"]),
        pandora_id=str(row["pandora_id"]),
        spotify_id=str(spotify_id) if spotify_id else None,
        name=str(row["name"]),
        genres=_parse_json_list(row["genres"]),
        popularity=int(row["popularity"] or 0),
        followers=int(row["followers"] or 0),
        image_url=row["image_url"],
        sentiment=str(row["sentiment"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _artist_ids_from_details(details: ArtistDetails) -> tuple[str, str | None]:
    if details.spotify_id.startswith("pandora-"):
        return details.spotify_id, None
    return pandora_artist_id(details.name), details.spotify_id


def _find_taste_artist_row(conn: Any, artist_key: str) -> Any | None:
    return conn.execute(
        """
        SELECT * FROM taste_artists
        WHERE pandora_id = ? OR spotify_id = ?
        LIMIT 1
        """,
        (artist_key, artist_key),
    ).fetchone()


def _get_taste_artist_by_key(artist_key: str, config: HubConfig | None = None) -> TasteArtist | None:
    ensure_db(config)
    with connect(config=config) as conn:
        row = _find_taste_artist_row(conn, artist_key)
    return _row_to_taste_artist(row) if row else None


def _row_to_artist_top_track(row: Any) -> ArtistTopTrack:
    return ArtistTopTrack(
        rank=int(row["rank"]),
        spotify_id=str(row["track_spotify_id"]),
        title=str(row["title"]),
        artist=str(row["artist"]),
        album=str(row["album"] or ""),
        year=int(row["year"]) if row["year"] is not None else None,
        image_url=row["image_url"],
        preview_url=row["preview_url"],
    )


def _delete_artist_top_tracks(artist_pandora_id: str, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute(
            "DELETE FROM taste_artist_top_tracks WHERE artist_pandora_id = ?",
            (artist_pandora_id,),
        )


def _save_artist_top_tracks(
    artist_pandora_id: str,
    tracks: list[TrackDetails],
    config: HubConfig | None = None,
) -> None:
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        conn.execute(
            "DELETE FROM taste_artist_top_tracks WHERE artist_pandora_id = ?",
            (artist_pandora_id,),
        )
        for rank, track in enumerate(tracks[:5], start=1):
            conn.execute(
                """
                INSERT INTO taste_artist_top_tracks
                (artist_pandora_id, rank, track_spotify_id, title, artist, album, year,
                 image_url, preview_url, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    artist_pandora_id,
                    rank,
                    track.spotify_id,
                    track.title,
                    track.artist,
                    track.album,
                    track.year,
                    track.image_url,
                    track.preview_url,
                    now,
                    now,
                ),
            )


def _refresh_artist_top_tracks(artist: TasteArtist, config: HubConfig | None = None) -> None:
    catalog_id = artist.spotify_id
    if not catalog_id or not is_spotify_catalog_id(catalog_id):
        _delete_artist_top_tracks(artist.pandora_id, config=config)
        return
    try:
        tracks = get_artist_top_tracks_with_fallback(catalog_id, limit=5, config=config)
    except SpotifyError:
        tracks = []
    if tracks:
        _save_artist_top_tracks(artist.pandora_id, tracks, config=config)
    else:
        _delete_artist_top_tracks(artist.pandora_id, config=config)


def list_artist_top_tracks(
    artist_key: str,
    config: HubConfig | None = None,
) -> list[ArtistTopTrack]:
    ensure_db(config)
    artist = _get_taste_artist_by_key(artist_key, config=config)
    pandora_id = artist.pandora_id if artist else artist_key
    with connect(config=config) as conn:
        rows = conn.execute(
            """
            SELECT rank, track_spotify_id, title, artist, album, year, image_url, preview_url
            FROM taste_artist_top_tracks
            WHERE artist_pandora_id = ?
            ORDER BY rank
            """,
            (pandora_id,),
        ).fetchall()
    return [_row_to_artist_top_track(row) for row in rows]


def refresh_artist_top_tracks(
    artist_key: str,
    config: HubConfig | None = None,
) -> list[ArtistTopTrack]:
    artist = _get_taste_artist_by_key(artist_key, config=config)
    if artist is None:
        return []
    _refresh_artist_top_tracks(artist, config=config)
    return list_artist_top_tracks(artist.pandora_id, config=config)


def refresh_artist_top_tracks_from_catalog(
    artist_key: str,
    catalog_artist_id: str,
    config: HubConfig | None = None,
) -> list[ArtistTopTrack]:
    """Fetch top tracks from a real Spotify artist ID and store under the taste artist."""
    artist = _get_taste_artist_by_key(artist_key, config=config)
    if artist is None:
        return []
    if is_spotify_catalog_id(catalog_artist_id):
        update_taste_artist_spotify_id(artist.pandora_id, catalog_artist_id, config=config)
        artist = _get_taste_artist_by_key(artist.pandora_id, config=config)
        if artist is None:
            return []
    _refresh_artist_top_tracks(artist, config=config)
    return list_artist_top_tracks(artist.pandora_id, config=config)


def update_taste_artist_spotify_id(
    pandora_id: str,
    catalog_spotify_id: str,
    config: HubConfig | None = None,
) -> TasteArtist | None:
    if not is_spotify_catalog_id(catalog_spotify_id):
        return _get_taste_artist_by_key(pandora_id, config=config)
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        conn.execute(
            """
            UPDATE taste_artists
            SET spotify_id = ?, updated_at = ?
            WHERE pandora_id = ?
            """,
            (catalog_spotify_id, now, pandora_id),
        )
    return _get_taste_artist_by_key(pandora_id, config=config)


def link_missing_liked_artist_spotify_ids(
    config: HubConfig | None = None,
) -> tuple[int, int]:
    """Link Spotify catalog IDs for liked artists using sibling artist matches."""
    liked_artists = list_liked_artists(config)
    linked = 0
    for artist in liked_artists:
        if artist.spotify_id:
            continue
        catalog_id = resolve_catalog_id_from_sibling_artists(artist, liked_artists)
        if not catalog_id:
            continue
        update_taste_artist_spotify_id(artist.pandora_id, catalog_id, config=config)
        linked += 1
    remaining = sum(1 for artist in list_liked_artists(config) if not artist.spotify_id)
    return linked, remaining


def update_taste_artist_genres(
    pandora_id: str,
    genres: list[str],
    config: HubConfig | None = None,
) -> None:
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        conn.execute(
            """
            UPDATE taste_artists
            SET genres = ?, updated_at = ?
            WHERE pandora_id = ?
            """,
            (_json_dumps(genres), now, pandora_id),
        )


def update_taste_song_genres(
    spotify_id: str,
    genres: list[str],
    config: HubConfig | None = None,
) -> None:
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        conn.execute(
            """
            UPDATE taste_songs
            SET genres = ?, updated_at = ?
            WHERE spotify_id = ?
            """,
            (_json_dumps(genres), now, spotify_id),
        )


def _normalize_artist_display(name: str) -> str:
    return name.replace("\u202f", ",").replace("\u00a0", " ").strip()


def _collaborator_names(artist_name: str) -> list[str]:
    normalized = _normalize_artist_display(artist_name)
    if not normalized:
        return []
    return [part.strip() for part in normalized.split(",") if part.strip()]


def _primary_artist_name(artist_name: str) -> str:
    names = _collaborator_names(artist_name)
    return names[0] if names else ""


def _genres_from_liked_artist_match(
    artist_name: str,
    liked_artists: list[TasteArtist],
) -> list[str]:
    def normalize(value: str) -> str:
        cleaned = _normalize_music_text(value)
        if cleaned.startswith("the "):
            cleaned = cleaned[4:]
        return cleaned

    candidates = _collaborator_names(artist_name) or ([artist_name] if artist_name else [])
    for candidate in candidates:
        target = normalize(candidate)
        for liked in liked_artists:
            if not liked.genres:
                continue
            liked_name = normalize(liked.name)
            if (
                target == liked_name
                or target in liked_name
                or liked_name in target
            ):
                return list(liked.genres)
    return []


def refresh_taste_artist_genres(
    artist_key: str,
    config: HubConfig | None = None,
) -> list[str]:
    artist = _get_taste_artist_by_key(artist_key, config=config)
    if artist is None:
        return []
    genres = get_artist_genres_with_fallback(
        artist.spotify_id or "",
        artist_name=artist.name,
        config=config,
    )
    if genres:
        update_taste_artist_genres(artist.pandora_id, genres, config=config)
    return genres


def refresh_taste_song_genres(
    song_spotify_id: str,
    config: HubConfig | None = None,
    *,
    liked_artists: list[TasteArtist] | None = None,
) -> list[str]:
    ensure_db(config)
    with connect(config=config) as conn:
        row = conn.execute(
            "SELECT * FROM taste_songs WHERE spotify_id = ?",
            (song_spotify_id,),
        ).fetchone()
    if row is None:
        return []
    song = _row_to_taste_song(row)
    liked_artists = liked_artists if liked_artists is not None else list_liked_artists(config)

    genres: list[str] = []
    if song.artist_id and is_spotify_catalog_id(song.artist_id):
        genres = get_artist_genres_with_fallback(
            song.artist_id,
            artist_name=song.artist,
            config=config,
        )
    elif is_spotify_catalog_id(song.spotify_id):
        try:
            track = fetch_track_details_from_embed(song.spotify_id)
            if track.artist_id:
                genres = get_artist_genres_with_fallback(
                    track.artist_id,
                    artist_name=track.artist,
                    config=config,
                )
        except SpotifyError:
            pass

    if not genres:
        genres = _genres_from_liked_artist_match(song.artist, liked_artists)

    if genres:
        update_taste_song_genres(song.spotify_id, genres, config=config)
    return genres


def backfill_taste_genres(config: HubConfig | None = None) -> tuple[int, int]:
    """Refresh genres for all liked artists and songs. Returns (artists, songs) updated."""
    artists_updated = 0
    for artist in list_liked_artists(config):
        if refresh_taste_artist_genres(artist.pandora_id, config=config):
            artists_updated += 1

    liked_artists = list_liked_artists(config)
    songs_updated = 0
    for song in list_liked_songs(config):
        if refresh_taste_song_genres(
            song.spotify_id,
            config=config,
            liked_artists=liked_artists,
        ):
            songs_updated += 1
    return artists_updated, songs_updated


def _resolve_item_genres(
    *,
    artist_id: str,
    artist_name: str,
    existing_genres: list[str],
    config: HubConfig | None,
    liked_artists: list[TasteArtist],
    cache: dict[str, list[str]],
    limit: int = 8,
) -> list[str]:
    if existing_genres:
        return existing_genres
    cache_key = (
        artist_id
        if artist_id and is_spotify_catalog_id(artist_id)
        else _normalize_music_text(artist_name)
    )
    if cache_key in cache:
        return cache[cache_key]

    genres: list[str] = []
    if artist_id and is_spotify_catalog_id(artist_id):
        genres = get_artist_genres_with_fallback(
            artist_id,
            artist_name=artist_name,
            config=config,
            limit=limit,
        )
    if not genres:
        genres = _genres_from_liked_artist_match(artist_name, liked_artists)
    if not genres and artist_name:
        genres = get_artist_genres_with_fallback(
            "",
            artist_name=artist_name,
            config=config,
            limit=limit,
        )

    cache[cache_key] = genres
    return genres


def _track_with_genres(track: TrackDetails, genres: list[str]) -> TrackDetails:
    if not genres or track.genres:
        return track
    return TrackDetails(
        spotify_id=track.spotify_id,
        title=track.title,
        artist=track.artist,
        artist_id=track.artist_id,
        album=track.album,
        year=track.year,
        genres=genres,
        energy=track.energy,
        valence=track.valence,
        danceability=track.danceability,
        tempo=track.tempo,
        popularity=track.popularity,
        duration_ms=track.duration_ms,
        image_url=track.image_url,
        preview_url=track.preview_url,
        source_rank=track.source_rank,
    )


def _artist_with_genres(artist: ArtistDetails, genres: list[str]) -> ArtistDetails:
    if not genres or artist.genres:
        return artist
    return ArtistDetails(
        spotify_id=artist.spotify_id,
        name=artist.name,
        genres=genres,
        popularity=artist.popularity,
        followers=artist.followers,
        image_url=artist.image_url,
    )


def resolve_track_genres(
    track: TrackDetails,
    config: HubConfig | None = None,
    *,
    genre_cache: dict[str, list[str]] | None = None,
    liked_artists: list[TasteArtist] | None = None,
) -> list[str]:
    """Resolve genres for a track from stored tags, artist IDs, or collaborators."""
    if track.genres:
        return list(track.genres)

    track = _ensure_track_artist_id(track, config=config)
    liked_artists = liked_artists if liked_artists is not None else list_liked_artists(config)
    cache = genre_cache if genre_cache is not None else {}

    primary = _primary_artist_name(track.artist) or track.artist
    genres = _resolve_item_genres(
        artist_id=track.artist_id,
        artist_name=primary,
        existing_genres=[],
        config=config,
        liked_artists=liked_artists,
        cache=cache,
    )
    if genres:
        return genres

    if is_spotify_catalog_id(track.spotify_id):
        try:
            artist_ids = fetch_track_artist_ids_from_embed(track.spotify_id)
        except SpotifyError:
            artist_ids = []
        for artist_id in artist_ids:
            if artist_id == track.artist_id:
                continue
            genres = _resolve_item_genres(
                artist_id=artist_id,
                artist_name="",
                existing_genres=[],
                config=config,
                liked_artists=liked_artists,
                cache=cache,
            )
            if genres:
                return genres

    for name in _collaborator_names(track.artist):
        if name == primary:
            continue
        genres = _resolve_item_genres(
            artist_id="",
            artist_name=name,
            existing_genres=[],
            config=config,
            liked_artists=liked_artists,
            cache=cache,
        )
        if genres:
            return genres
    return []


def resolve_display_genres(
    artist_id: str,
    artist_name: str,
    config: HubConfig | None = None,
    *,
    existing_genres: list[str] | None = None,
    genre_cache: dict[str, list[str]] | None = None,
    liked_artists: list[TasteArtist] | None = None,
) -> list[str]:
    """Resolve Spotify-style genres for display, using liked-artist matches and lookups."""
    if existing_genres:
        return list(existing_genres)
    primary_name = _primary_artist_name(artist_name) or artist_name
    liked_artists = liked_artists if liked_artists is not None else list_liked_artists(config)
    return _resolve_item_genres(
        artist_id=artist_id,
        artist_name=primary_name,
        existing_genres=[],
        config=config,
        liked_artists=liked_artists,
        cache=genre_cache if genre_cache is not None else {},
    )


def _ensure_track_artist_id(track: TrackDetails, config: HubConfig | None = None) -> TrackDetails:
    if track.artist_id or not is_spotify_catalog_id(track.spotify_id):
        return track
    try:
        embed = fetch_track_details_from_embed(track.spotify_id)
    except SpotifyError:
        return track
    if not embed.artist_id:
        return track
    return TrackDetails(
        spotify_id=track.spotify_id,
        title=track.title,
        artist=track.artist,
        artist_id=embed.artist_id,
        album=track.album or embed.album,
        year=track.year or embed.year,
        genres=track.genres,
        energy=track.energy,
        valence=track.valence,
        danceability=track.danceability,
        tempo=track.tempo,
        popularity=track.popularity,
        duration_ms=track.duration_ms,
        image_url=track.image_url or embed.image_url,
        preview_url=track.preview_url or embed.preview_url,
        source_rank=track.source_rank,
    )


def _seed_genre_cache_from_taste(
    liked_artists: list[TasteArtist],
    liked_songs: list[TasteSong],
) -> dict[str, list[str]]:
    cache: dict[str, list[str]] = {}
    for artist in liked_artists:
        if not artist.genres:
            continue
        cache_key = (
            artist.spotify_id
            if artist.spotify_id and is_spotify_catalog_id(artist.spotify_id)
            else _normalize_music_text(artist.name)
        )
        cache[cache_key] = list(artist.genres)
    for song in liked_songs:
        if not song.genres:
            continue
        primary = _primary_artist_name(song.artist) or song.artist
        cache_key = (
            song.artist_id
            if song.artist_id and is_spotify_catalog_id(song.artist_id)
            else _normalize_music_text(primary)
        )
        if cache_key not in cache:
            cache[cache_key] = list(song.genres)
    return cache


def _prefetch_track_details_cache(
    track_ids: list[str],
    *,
    embed_track_cache: dict[str, TrackDetails],
    wild_card_cache: dict[str, TrackDetails],
    config: HubConfig | None,
) -> dict[str, TrackDetails]:
    details_cache: dict[str, TrackDetails] = {}
    details_cache.update(embed_track_cache)
    details_cache.update(wild_card_cache)
    missing = [track_id for track_id in track_ids if track_id not in details_cache]
    if missing:
        workers = (
            EMBED_PARALLEL_WORKERS
            if not spotify_web_api_available(config)
            else 8
        )

        def _fetch_one(track_id: str) -> TrackDetails | None:
            try:
                return get_track_details_with_fallback(track_id, config=config)
            except SpotifyError:
                return None

        for track_id, track in zip(missing, map_parallel(missing, _fetch_one, max_workers=workers)):
            if track is not None:
                details_cache[track_id] = track
    needing_id = [
        track
        for track in details_cache.values()
        if not track.artist_id and is_spotify_catalog_id(track.spotify_id)
    ]
    if needing_id:
        for track in map_parallel(
            needing_id,
            lambda item: _ensure_track_artist_id(item, config=config),
            max_workers=EMBED_PARALLEL_WORKERS,
        ):
            if track is not None:
                details_cache[track.spotify_id] = track
    return details_cache


def _prefetch_genres_for_details(
    details_cache: dict[str, TrackDetails],
    genre_cache: dict[str, list[str]],
    *,
    liked_artists: list[TasteArtist],
    config: HubConfig | None,
) -> None:
    tasks: list[tuple[str, str]] = []
    seen: set[str] = set()
    for track in details_cache.values():
        primary = _primary_artist_name(track.artist) or track.artist
        cache_key = (
            track.artist_id
            if track.artist_id and is_spotify_catalog_id(track.artist_id)
            else _normalize_music_text(primary)
        )
        if cache_key in genre_cache or cache_key in seen:
            continue
        seen.add(cache_key)
        tasks.append((track.artist_id, primary))

    def _fetch_genres(task: tuple[str, str]) -> None:
        artist_id, name = task
        _resolve_item_genres(
            artist_id=artist_id,
            artist_name=name,
            existing_genres=[],
            config=config,
            liked_artists=liked_artists,
            cache=genre_cache,
        )

    if tasks:
        map_parallel(tasks, _fetch_genres, max_workers=4)


def _row_to_wishlist_song(row: Any) -> WishlistSong:
    return WishlistSong(
        id=int(row["id"]),
        spotify_id=str(row["spotify_id"]),
        title=str(row["title"]),
        artist=str(row["artist"]),
        artist_id=str(row["artist_id"] or ""),
        album=str(row["album"] or ""),
        year=int(row["year"]) if row["year"] is not None else None,
        genres=_parse_json_list(row["genres"]),
        energy=float(row["energy"]) if row["energy"] is not None else None,
        valence=float(row["valence"]) if row["valence"] is not None else None,
        danceability=float(row["danceability"]) if row["danceability"] is not None else None,
        tempo=float(row["tempo"]) if row["tempo"] is not None else None,
        popularity=int(row["popularity"] or 0),
        duration_ms=int(row["duration_ms"]) if row["duration_ms"] is not None else None,
        image_url=row["image_url"],
        preview_url=row["preview_url"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_wishlist_artist(row: Any) -> WishlistArtist:
    return WishlistArtist(
        id=int(row["id"]),
        spotify_id=str(row["spotify_id"]),
        name=str(row["name"]),
        genres=_parse_json_list(row["genres"]),
        popularity=int(row["popularity"] or 0),
        followers=int(row["followers"] or 0),
        image_url=row["image_url"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _upsert_taste_song(details: TrackDetails, sentiment: str, config: HubConfig | None = None) -> TasteSong:
    if sentiment not in {"like", "dislike"}:
        raise MusicValidationError("Sentiment must be 'like' or 'dislike'.")
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        existing = conn.execute(
            "SELECT id FROM taste_songs WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE taste_songs
                SET title=?, artist=?, artist_id=?, album=?, year=?, genres=?,
                    energy=?, valence=?, danceability=?, tempo=?, popularity=?,
                    duration_ms=?, image_url=?, preview_url=?, sentiment=?, updated_at=?
                WHERE spotify_id=?
                """,
                (
                    details.title, details.artist, details.artist_id, details.album,
                    details.year, _json_dumps(details.genres), details.energy, details.valence,
                    details.danceability, details.tempo, details.popularity, details.duration_ms,
                    details.image_url, details.preview_url, sentiment, now, details.spotify_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO taste_songs
                (spotify_id, title, artist, artist_id, album, year, genres,
                 energy, valence, danceability, tempo, popularity, duration_ms,
                 image_url, preview_url, sentiment, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    details.spotify_id, details.title, details.artist, details.artist_id,
                    details.album, details.year, _json_dumps(details.genres), details.energy,
                    details.valence, details.danceability, details.tempo, details.popularity,
                    details.duration_ms, details.image_url, details.preview_url,
                    sentiment, now, now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM taste_songs WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
    return _row_to_taste_song(row)


def _upsert_taste_artist(details: ArtistDetails, sentiment: str, config: HubConfig | None = None) -> TasteArtist:
    if sentiment not in {"like", "dislike"}:
        raise MusicValidationError("Sentiment must be 'like' or 'dislike'.")
    ensure_db(config)
    pandora_id, catalog_id = _artist_ids_from_details(details)
    now = utc_now_iso()
    with connect(config=config) as conn:
        existing = conn.execute(
            """
            SELECT * FROM taste_artists
            WHERE pandora_id = ? OR (spotify_id IS NOT NULL AND spotify_id = ?)
               OR lower(trim(name)) = lower(trim(?))
            LIMIT 1
            """,
            (pandora_id, catalog_id or "", details.name),
        ).fetchone()
        if existing:
            merged_catalog = catalog_id or existing["spotify_id"]
            conn.execute(
                """
                UPDATE taste_artists
                SET pandora_id=?, spotify_id=?, name=?, genres=?, popularity=?, followers=?,
                    image_url=?, sentiment=?, updated_at=?
                WHERE id=?
                """,
                (
                    str(existing["pandora_id"]),
                    merged_catalog,
                    details.name,
                    _json_dumps(details.genres),
                    details.popularity,
                    details.followers,
                    details.image_url,
                    sentiment,
                    now,
                    existing["id"],
                ),
            )
            row = conn.execute(
                "SELECT * FROM taste_artists WHERE id = ?",
                (existing["id"],),
            ).fetchone()
        else:
            conn.execute(
                """
                INSERT INTO taste_artists
                (pandora_id, spotify_id, name, genres, popularity, followers, image_url,
                 sentiment, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    pandora_id,
                    catalog_id,
                    details.name,
                    _json_dumps(details.genres),
                    details.popularity,
                    details.followers,
                    details.image_url,
                    sentiment,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM taste_artists WHERE pandora_id = ?",
                (pandora_id,),
            ).fetchone()
    return _row_to_taste_artist(row)


def add_song(spotify_id: str, sentiment: str, config: HubConfig | None = None) -> TasteSong:
    try:
        details = get_track_details(spotify_id, config=config)
    except SpotifyError:
        details = get_track_details_with_fallback(spotify_id, config=config)
    song = _upsert_taste_song(details, sentiment, config=config)
    if not song.genres:
        refresh_taste_song_genres(song.spotify_id, config=config)
        refreshed = list_liked_songs(config)
        song = next((s for s in refreshed if s.spotify_id == song.spotify_id), song)
    return song


def add_artist(spotify_id: str, sentiment: str, config: HubConfig | None = None) -> TasteArtist:
    try:
        details = get_artist_details(spotify_id, config=config)
    except SpotifyError:
        details = get_artist_details_with_fallback(spotify_id, config=config)
    artist = _upsert_taste_artist(details, sentiment, config=config)
    if not artist.genres:
        refresh_taste_artist_genres(artist.pandora_id, config=config)
        artist = _get_taste_artist_by_key(artist.pandora_id, config=config) or artist
    if sentiment == "like":
        _refresh_artist_top_tracks(artist, config=config)
    else:
        _delete_artist_top_tracks(artist.pandora_id, config=config)
    return artist


def remove_song(spotify_id: str, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute("DELETE FROM taste_songs WHERE spotify_id = ?", (spotify_id,))


def remove_artist(artist_key: str, config: HubConfig | None = None) -> None:
    ensure_db(config)
    artist = _get_taste_artist_by_key(artist_key, config=config)
    if artist is None:
        return
    with connect(config=config) as conn:
        conn.execute("DELETE FROM taste_artists WHERE id = ?", (artist.id,))
    _delete_artist_top_tracks(artist.pandora_id, config=config)


def list_taste_songs(sentiment: str | None = None, config: HubConfig | None = None) -> list[TasteSong]:
    ensure_db(config)
    with connect(config=config) as conn:
        if sentiment:
            rows = conn.execute(
                "SELECT * FROM taste_songs WHERE sentiment=? ORDER BY title COLLATE NOCASE",
                (sentiment,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM taste_songs ORDER BY sentiment, title COLLATE NOCASE"
            ).fetchall()
    return [_row_to_taste_song(row) for row in rows]


def list_taste_artists(sentiment: str | None = None, config: HubConfig | None = None) -> list[TasteArtist]:
    ensure_db(config)
    with connect(config=config) as conn:
        if sentiment:
            rows = conn.execute(
                "SELECT * FROM taste_artists WHERE sentiment=? ORDER BY name COLLATE NOCASE",
                (sentiment,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM taste_artists ORDER BY sentiment, name COLLATE NOCASE"
            ).fetchall()
    return [_row_to_taste_artist(row) for row in rows]


def list_liked_songs(config: HubConfig | None = None) -> list[TasteSong]:
    return list_taste_songs("like", config=config)


def list_disliked_songs(config: HubConfig | None = None) -> list[TasteSong]:
    return list_taste_songs("dislike", config=config)


def list_liked_artists(config: HubConfig | None = None) -> list[TasteArtist]:
    return list_taste_artists("like", config=config)


def list_disliked_artists(config: HubConfig | None = None) -> list[TasteArtist]:
    return list_taste_artists("dislike", config=config)


def _upsert_wishlist_song(details: TrackDetails, config: HubConfig | None = None) -> WishlistSong:
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        existing = conn.execute(
            "SELECT id FROM wishlist_songs WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE wishlist_songs
                SET title=?, artist=?, artist_id=?, album=?, year=?, genres=?,
                    energy=?, valence=?, danceability=?, tempo=?, popularity=?,
                    duration_ms=?, image_url=?, preview_url=?, updated_at=?
                WHERE spotify_id=?
                """,
                (
                    details.title, details.artist, details.artist_id, details.album,
                    details.year, _json_dumps(details.genres), details.energy, details.valence,
                    details.danceability, details.tempo, details.popularity, details.duration_ms,
                    details.image_url, details.preview_url, now, details.spotify_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO wishlist_songs
                (spotify_id, title, artist, artist_id, album, year, genres,
                 energy, valence, danceability, tempo, popularity, duration_ms,
                 image_url, preview_url, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    details.spotify_id, details.title, details.artist, details.artist_id,
                    details.album, details.year, _json_dumps(details.genres), details.energy,
                    details.valence, details.danceability, details.tempo, details.popularity,
                    details.duration_ms, details.image_url, details.preview_url, now, now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM wishlist_songs WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
    return _row_to_wishlist_song(row)


def _upsert_wishlist_artist(details: ArtistDetails, config: HubConfig | None = None) -> WishlistArtist:
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        existing = conn.execute(
            "SELECT id FROM wishlist_artists WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE wishlist_artists
                SET name=?, genres=?, popularity=?, followers=?, image_url=?, updated_at=?
                WHERE spotify_id=?
                """,
                (
                    details.name, _json_dumps(details.genres), details.popularity,
                    details.followers, details.image_url, now, details.spotify_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO wishlist_artists
                (spotify_id, name, genres, popularity, followers, image_url, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    details.spotify_id, details.name, _json_dumps(details.genres),
                    details.popularity, details.followers, details.image_url, now, now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM wishlist_artists WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
    return _row_to_wishlist_artist(row)


def add_song_to_wishlist(spotify_id: str, config: HubConfig | None = None) -> WishlistSong:
    details = get_track_details(spotify_id, config=config)
    return _upsert_wishlist_song(details, config=config)


def add_artist_to_wishlist(spotify_id: str, config: HubConfig | None = None) -> WishlistArtist:
    details = get_artist_details(spotify_id, config=config)
    return _upsert_wishlist_artist(details, config=config)


def remove_song_from_wishlist(spotify_id: str, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute("DELETE FROM wishlist_songs WHERE spotify_id = ?", (spotify_id,))


def remove_artist_from_wishlist(spotify_id: str, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute("DELETE FROM wishlist_artists WHERE spotify_id = ?", (spotify_id,))


def list_wishlist_songs(config: HubConfig | None = None) -> list[WishlistSong]:
    ensure_db(config)
    with connect(config=config) as conn:
        rows = conn.execute(
            "SELECT * FROM wishlist_songs ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_wishlist_song(row) for row in rows]


def list_wishlist_artists(config: HubConfig | None = None) -> list[WishlistArtist]:
    ensure_db(config)
    with connect(config=config) as conn:
        rows = conn.execute(
            "SELECT * FROM wishlist_artists ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_wishlist_artist(row) for row in rows]


def search_songs(query: str, config: HubConfig | None = None):  # type: ignore[return]
    return search_tracks(query, config=config)


def search_artists_query(query: str, config: HubConfig | None = None):  # type: ignore[return]
    return search_artists(query, config=config)


def get_spotify_genres(config: HubConfig | None = None) -> list[str]:
    """Return genre options for UI filters (Spotify seeds plus taste-profile tags)."""
    if not spotify_configured(config):
        raise SpotifyConfigError("Spotify is not configured.")
    genres = {g.lower() for g in get_available_genre_seeds(config=config) if g}
    for artist in list_liked_artists(config):
        genres.update(g.lower() for g in artist.genres if g)
    for song in list_liked_songs(config):
        genres.update(g.lower() for g in song.genres if g)
    return sorted(genres)


def import_liked_songs_from_playlist(
    playlist: str,
    config: HubConfig | None = None,
) -> tuple[int, int, list[str]]:
    """Import tracks from a public Spotify playlist URL/ID into liked songs."""
    ensure_db(config)
    tracks = fetch_playlist_tracks_from_embed(playlist, config=config)
    existing = {song.spotify_id for song in list_liked_songs(config)}
    added = 0
    skipped = 0
    titles: list[str] = []
    for track in tracks:
        if track.spotify_id in existing:
            skipped += 1
            continue
        _upsert_taste_song(track, "like", config=config)
        existing.add(track.spotify_id)
        added += 1
        titles.append(f"{track.title} — {track.artist}")
    return added, skipped, titles


def add_liked_song_metadata(
    title: str,
    artist: str,
    config: HubConfig | None = None,
) -> TasteSong:
    ensure_db(config)
    details = track_details_from_pandora(title, artist)
    return _upsert_taste_song(details, "like", config=config)


def import_liked_songs_from_pandora_tracks(
    tracks: list[tuple[str, str]],
    config: HubConfig | None = None,
) -> tuple[int, int, list[str]]:
    ensure_db(config)
    existing = {song.spotify_id for song in list_liked_songs(config)}
    added = 0
    skipped = 0
    titles: list[str] = []
    for title, artist in tracks:
        details = track_details_from_pandora(title, artist)
        if details.spotify_id in existing:
            skipped += 1
            continue
        _upsert_taste_song(details, "like", config=config)
        existing.add(details.spotify_id)
        added += 1
        titles.append(f"{title} — {artist}")
    return added, skipped, titles


def import_liked_songs_from_pandora_url(
    url: str,
    config: HubConfig | None = None,
) -> tuple[int, int, list[str]]:
    tracks = fetch_pandora_playlist_tracks(url)
    return import_liked_songs_from_pandora_tracks(tracks, config=config)


def _build_liked_sets(
    liked_songs: list[TasteSong],
    disliked_songs: list[TasteSong],
    liked_artists: list[TasteArtist],
    disliked_artists: list[TasteArtist],
) -> tuple[set[str], set[str], list[float], list[float], list[float], set[str], set[str], list[int]]:
    liked_genres: set[str] = set()
    for s in liked_songs:
        liked_genres.update(g.lower() for g in s.genres)
    for a in liked_artists:
        liked_genres.update(g.lower() for g in a.genres)

    disliked_genres: set[str] = set()
    for s in disliked_songs:
        disliked_genres.update(g.lower() for g in s.genres)
    for a in disliked_artists:
        disliked_genres.update(g.lower() for g in a.genres)

    liked_energy = [s.energy for s in liked_songs if s.energy is not None]
    liked_valence = [s.valence for s in liked_songs if s.valence is not None]
    liked_danceability = [s.danceability for s in liked_songs if s.danceability is not None]

    liked_artist_ids = {s.artist_id for s in liked_songs if s.artist_id}
    liked_artist_ids.update(
        a.spotify_id for a in liked_artists if a.spotify_id and is_spotify_catalog_id(a.spotify_id)
    )

    disliked_artist_ids = {s.artist_id for s in disliked_songs if s.artist_id}
    disliked_artist_ids.update(
        a.spotify_id for a in disliked_artists if a.spotify_id and is_spotify_catalog_id(a.spotify_id)
    )

    liked_years = [s.year for s in liked_songs if s.year is not None]

    return (
        liked_genres, disliked_genres,
        liked_energy, liked_valence, liked_danceability,
        liked_artist_ids, disliked_artist_ids,
        liked_years,
    )


def _normalize_music_text(value: str) -> str:
    return " ".join(value.lower().split())


def _normalize_artist_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.lower().strip())
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return normalized


def _artist_lookup_name(name: str) -> str:
    cleaned = re.sub(r"\s+explicit$", "", name, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.endswith("(Dance)"):
        cleaned = cleaned[: -len("(Dance)")].strip()
    return cleaned


_MANUAL_SPOTIFY_ARTIST_IDS: dict[str, str] = {
    _normalize_artist_name("Dimond Saints"): "38LWle0ChG6k0UHsOnoO75",
    _normalize_artist_name("Israel Kamakawiwo'ole"): "4ogvuDRerGhZfSf7TtzHlr",
    _normalize_artist_name("Spafford"): "7fA0IDinGo27lmOeGy6oGV",
}


def resolve_manual_catalog_artist_id(name: str) -> str | None:
    return _MANUAL_SPOTIFY_ARTIST_IDS.get(_normalize_artist_name(_artist_lookup_name(name)))


def resolve_catalog_id_from_sibling_artists(
    artist: TasteArtist,
    liked_artists: list[TasteArtist],
) -> str | None:
    """Reuse a linked Spotify catalog ID from a closely matching liked artist name."""
    lookup_name = _artist_lookup_name(artist.name)
    lookup_norm = _normalize_artist_name(lookup_name)

    best_match: str | None = None
    best_score = 0
    for other in liked_artists:
        if other.pandora_id == artist.pandora_id or not other.spotify_id:
            continue
        other_lookup = _artist_lookup_name(other.name)
        other_norm = _normalize_artist_name(other_lookup)
        if lookup_norm == other_norm:
            return other.spotify_id
        if lookup_norm in other_norm or other_norm in lookup_norm:
            score = min(len(lookup_norm), len(other_norm))
            if score > best_score:
                best_score = score
                best_match = other.spotify_id
    return best_match


def is_collaboration_artist_name(name: str) -> bool:
    """True when a name looks like a multi-artist track credit, not a single act."""
    cleaned = re.sub(r"\s+explicit$", "", name.strip(), flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return False

    lower = cleaned.lower()
    if re.search(r",|\bfeat\.?\b|\bfeaturing\b|\bwith\b", lower):
        return True

    if " & " not in cleaned and not re.search(r"\band\b", lower):
        return False

    # Keep band names like "Andy Frasco & The U.N."
    if re.match(r"^.+\s&\s+The\s+", cleaned, re.IGNORECASE) and "," not in cleaned:
        if cleaned.count(" & ") == 1 and " feat" not in lower:
            return False

    return True


def remove_collaboration_liked_artists(config: HubConfig | None = None) -> list[TasteArtist]:
    """Remove liked artists whose names are multi-artist collaboration credits."""
    removed: list[TasteArtist] = []
    for artist in list_liked_artists(config):
        if is_collaboration_artist_name(artist.name):
            remove_artist(artist.pandora_id, config=config)
            removed.append(artist)
    return removed


def _normalize_song_title_base(title: str) -> str:
    """Reduce a track title to its core song name, stripping version suffixes."""
    cleaned = re.sub(r"\s+explicit$", "", title.strip(), flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", cleaned).strip()
    cleaned = re.sub(
        r"\s*-\s+(live|remaster(?:ed)?|remix|acoustic|radio edit|extended mix|"
        r"extended version|version|edit|demo|instrumental|live at|live in)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return _normalize_music_text(cleaned) or _normalize_music_text(title)


def _normalize_artist_base(artist: str) -> str:
    cleaned = re.sub(r"\s+explicit$", "", artist.strip(), flags=re.IGNORECASE)
    return _normalize_music_text(cleaned)


def _song_variation_key(title: str, artist: str) -> tuple[str, str]:
    return (_normalize_song_title_base(title), _normalize_artist_base(artist))


def _song_identity_key(title: str, artist: str) -> tuple[str, str]:
    return (_normalize_music_text(title), _normalize_music_text(artist))


def _track_is_liked(track: TrackDetails, liked_songs: list[TasteSong]) -> bool:
    variation_key = _song_variation_key(track.title, track.artist)
    for song in liked_songs:
        if song.spotify_id and song.spotify_id == track.spotify_id:
            return True
        if _song_identity_key(song.title, song.artist) == _song_identity_key(
            track.title, track.artist
        ):
            return True
        if _song_variation_key(song.title, song.artist) == variation_key:
            return True
    return False


def _artist_is_liked(artist: ArtistDetails, liked_artists: list[TasteArtist]) -> bool:
    norm_name = _normalize_music_text(artist.name)
    for liked in liked_artists:
        if liked.spotify_id and liked.spotify_id == artist.spotify_id:
            return True
        if liked.pandora_id == artist.spotify_id:
            return True
        if _normalize_music_text(liked.name) == norm_name:
            return True
    return False


def recommend(
    filters: MusicRecommendFilters,
    config: HubConfig | None = None,
) -> tuple[list[SongRecommendation], list[ArtistRecommendation]]:
    config = config or load_config()
    if not spotify_configured(config):
        raise MusicRecommendationError("Spotify is not configured.")

    liked_songs = list_liked_songs(config)
    disliked_songs = list_disliked_songs(config)
    liked_artists = list_liked_artists(config)
    disliked_artists = list_disliked_artists(config)

    if not liked_songs and not liked_artists:
        raise MusicRecommendationError(
            "Add at least one liked song or artist to get recommendations."
        )

    (
        liked_genres, disliked_genres,
        liked_energy, liked_valence, liked_danceability,
        liked_artist_ids, disliked_artist_ids,
        liked_years,
    ) = _build_liked_sets(liked_songs, disliked_songs, liked_artists, disliked_artists)

    taste_spotify_ids = {s.spotify_id for s in liked_songs + disliked_songs}

    explicit_liked_artist_ids = {
        a.spotify_id
        for a in liked_artists
        if a.spotify_id and is_spotify_catalog_id(a.spotify_id)
    }
    liked_song_text = [(s.title, s.artist) for s in liked_songs]

    weights = config.music_recommender.weights
    zone_cfg = config.music_recommender.zones
    explicit_genres = filters.genre_names or []
    search_genres = explicit_genres or sorted(liked_genres)[:3]

    # -----------------------------------------------------------------------
    # Zone 1 – SAFE: embed top-tracks from liked artists (familiar territory)
    # Zone 2 – STRETCH: genre search + Spotify Web API candidates (new styles)
    # Zone 3 – WILD CARD: new-release embed candidates (maximum novelty)
    # -----------------------------------------------------------------------
    embed_track_cache: dict[str, TrackDetails] = {}
    web_api = spotify_web_api_available(config)
    embed_max_artists = 12 if not web_api else 8

    # --- Zone 1 (Safe): embed top tracks from liked artists ---
    safe_ids: set[str] = set()
    embed_track_cache = collect_embed_recommendation_tracks(
        liked_songs,
        liked_artists,
        max_artists=embed_max_artists,
    )
    safe_ids.update(embed_track_cache.keys())

    # Enrich liked artist IDs from embed-resolved tracks for affinity scoring
    for song in liked_songs:
        if song.artist_id and is_spotify_catalog_id(song.artist_id):
            liked_artist_ids.add(song.artist_id)
        elif is_spotify_catalog_id(song.spotify_id):
            cached = embed_track_cache.get(song.spotify_id)
            if cached and cached.artist_id:
                liked_artist_ids.add(cached.artist_id)

    # --- Zone 2 (Stretch): Spotify Web API recs + genre search ---
    stretch_ids: set[str] = set()

    if web_api:
        seed_track_ids = [
            s.spotify_id for s in liked_songs if is_spotify_catalog_id(s.spotify_id)
        ][:2]
        seed_artist_ids_list = [
            a.spotify_id
            for a in liked_artists
            if a.spotify_id and is_spotify_catalog_id(a.spotify_id)
        ][:3]
        recs = get_spotify_recommendations(
            seed_track_ids=seed_track_ids or None,
            seed_artist_ids=seed_artist_ids_list or None,
            seed_genres=explicit_genres[:5] if explicit_genres else None,
            energy_min=(
                filters.energy_min if filters.include_energy and filters.energy_min > 0 else None
            ),
            energy_max=(
                filters.energy_max if filters.include_energy and filters.energy_max < 1 else None
            ),
            valence_min=(
                filters.valence_min if filters.include_valence and filters.valence_min > 0 else None
            ),
            valence_max=(
                filters.valence_max if filters.include_valence and filters.valence_max < 1 else None
            ),
            limit=50,
            config=config,
        )
        stretch_ids.update(recs)

        for artist in liked_artists[:5]:
            if not artist.spotify_id or not is_spotify_catalog_id(artist.spotify_id):
                continue
            top = get_artist_top_track_ids(artist.spotify_id, config=config)
            stretch_ids.update(top[:5])
        for song in liked_songs[:3]:
            if song.artist_id and is_spotify_catalog_id(song.artist_id):
                top = get_artist_top_track_ids(song.artist_id, config=config)
                stretch_ids.update(top[:3])

        for genre in search_genres[:3]:
            ids = search_tracks_by_genre(genre, limit=10, config=config)
            stretch_ids.update(ids)

    # Remove safe-zone tracks that are in stretch (they already got the safe treatment)
    stretch_ids -= safe_ids

    # --- Zone 3 (Wild Card): new releases embed ---
    wild_tracks = fetch_new_release_candidates(limit=40)
    wild_card_cache: dict[str, TrackDetails] = {t.spotify_id: t for t in wild_tracks}
    wild_ids: set[str] = set(wild_card_cache.keys()) - safe_ids - stretch_ids

    # --- Remove already-rated tracks from all zones ---
    def _clean(ids: set[str]) -> set[str]:
        return {tid for tid in ids - taste_spotify_ids if is_spotify_catalog_id(tid)}

    safe_ids = _clean(safe_ids)
    stretch_ids = _clean(stretch_ids)
    wild_ids = _clean(wild_ids)

    # -----------------------------------------------------------------------
    # Score candidates per zone
    # -----------------------------------------------------------------------
    liked_artist_names = {a.name for a in liked_artists}
    genre_cache = _seed_genre_cache_from_taste(liked_artists, liked_songs)
    score_cap = max(filters.song_count * 4, 20)
    safe_candidate_ids = sorted(safe_ids)[:score_cap]
    stretch_candidate_ids = sorted(stretch_ids)[:score_cap]
    wild_candidate_ids = sorted(wild_ids)[:score_cap]
    all_candidate_ids = list(
        dict.fromkeys(safe_candidate_ids + stretch_candidate_ids + wild_candidate_ids)
    )
    details_cache = _prefetch_track_details_cache(
        all_candidate_ids,
        embed_track_cache=embed_track_cache,
        wild_card_cache=wild_card_cache,
        config=config,
    )
    _prefetch_genres_for_details(
        details_cache,
        genre_cache,
        liked_artists=liked_artists,
        config=config,
    )

    def _score_track(
        track_id: str,
        zone_name: str,
        zone_weights_obj: Any,
        seen: set[str],
    ) -> SongRecommendation | None:
        if track_id in seen:
            return None
        seen.add(track_id)
        details = details_cache.get(track_id)
        if details is None:
            return None
        genres = resolve_track_genres(
            details,
            config=config,
            liked_artists=liked_artists,
            genre_cache=genre_cache,
        )
        details = _track_with_genres(details, genres)
        if _track_is_liked(details, liked_songs):
            return None
        if filters.include_year and details.year is not None and (
            details.year < filters.year_min or details.year > filters.year_max
        ):
            return None
        if explicit_genres:
            if not details.genres:
                return None
            if not any(
                g.lower() in {fg.lower() for fg in explicit_genres} for g in details.genres
            ):
                return None
        scr = song_score(
            candidate_genres=details.genres,
            candidate_energy=details.energy,
            candidate_valence=details.valence,
            candidate_danceability=details.danceability,
            candidate_artist_id=details.artist_id,
            candidate_year=details.year,
            candidate_popularity=details.popularity,
            liked_genres=liked_genres,
            disliked_genres=disliked_genres,
            liked_energy=liked_energy,
            liked_valence=liked_valence,
            liked_danceability=liked_danceability,
            liked_artist_ids=liked_artist_ids,
            related_artist_ids=set(),
            year_min=filters.year_min,
            year_max=filters.year_max,
            liked_years=liked_years,
            weights=weights,
            include_energy=filters.include_energy,
            include_valence=filters.include_valence,
            include_year=filters.include_year,
            taste_text_match=taste_text_similarity(details.title, details.artist, liked_song_text),
            explicit_liked_artist_ids=explicit_liked_artist_ids,
            source_rank=details.source_rank,
            zone_weights=zone_weights_obj,
        )
        reason = song_reason(
            candidate_title=details.title,
            candidate_artist=details.artist,
            candidate_genres=details.genres,
            candidate_energy=details.energy,
            candidate_valence=details.valence,
            candidate_year=details.year,
            score=scr,
            liked_genres=liked_genres,
            disliked_genres=disliked_genres,
            liked_artist_names=liked_artist_names,
            candidate_artist_in_liked=details.artist_id in liked_artist_ids,
            include_energy=filters.include_energy,
            include_valence=filters.include_valence,
            include_year=filters.include_year,
        )
        return SongRecommendation(track=details, score=scr, reason=reason, zone=zone_name)

    seen_track_ids: set[str] = set()

    safe_recs: list[SongRecommendation] = []
    for tid in safe_candidate_ids:
        rec = _score_track(tid, "safe", zone_cfg.safe, seen_track_ids)
        if rec:
            safe_recs.append(rec)
    safe_recs.sort(key=lambda x: x.score.total, reverse=True)

    stretch_recs: list[SongRecommendation] = []
    for tid in stretch_candidate_ids:
        rec = _score_track(tid, "stretch", zone_cfg.stretch, seen_track_ids)
        if rec:
            stretch_recs.append(rec)
    stretch_recs.sort(key=lambda x: x.score.total, reverse=True)

    wild_recs: list[SongRecommendation] = []
    for tid in wild_candidate_ids:
        rec = _score_track(tid, "wild_card", zone_cfg.wild_card, seen_track_ids)
        if rec:
            wild_recs.append(rec)
    wild_recs.sort(key=lambda x: x.score.total, reverse=True)

    # -----------------------------------------------------------------------
    # Merge zones: 40% Safe, 40% Stretch, 20% Wild Card — with backfill
    # -----------------------------------------------------------------------
    n = filters.song_count
    n_safe = max(1, round(n * 0.40))
    n_stretch = max(1, round(n * 0.40))
    n_wild = max(0, n - n_safe - n_stretch)

    def _take(pool: list[SongRecommendation], count: int) -> list[SongRecommendation]:
        return pool[:count]

    top_safe = _take(safe_recs, n_safe)
    top_stretch = _take(stretch_recs, n_stretch)
    top_wild = _take(wild_recs, n_wild)

    # Backfill short zones from remaining pool items (preserve zone labels)
    shortage = n - len(top_safe) - len(top_stretch) - len(top_wild)
    if shortage > 0:
        used_ids = {r.track.spotify_id for r in top_safe + top_stretch + top_wild}
        backfill_pool = (
            [r for r in safe_recs[n_safe:] if r.track.spotify_id not in used_ids]
            + [r for r in stretch_recs[n_stretch:] if r.track.spotify_id not in used_ids]
            + [r for r in wild_recs[n_wild:] if r.track.spotify_id not in used_ids]
        )
        backfill_pool.sort(key=lambda x: x.score.total, reverse=True)
        top_safe += backfill_pool[:shortage]

    top_songs = [
        rec for rec in (top_safe + top_stretch + top_wild)
        if not _track_is_liked(rec.track, liked_songs)
    ]

    # --- Artist candidates ---
    candidate_artist_ids: set[str] = set()
    taste_artist_ids_all = {
        artist_id
        for artist in liked_artists + disliked_artists
        for artist_id in (artist.spotify_id, artist.pandora_id)
        if artist_id
    }

    # Resolve artist IDs for liked songs that are missing them (embed fallback)
    resolved_artist_ids: set[str] = set()
    songs_needing_artist_embed: list[str] = []
    for song in liked_songs:
        if song.artist_id and is_spotify_catalog_id(song.artist_id):
            resolved_artist_ids.add(song.artist_id)
        elif is_spotify_catalog_id(song.spotify_id):
            cached = embed_track_cache.get(song.spotify_id)
            if cached and cached.artist_id:
                resolved_artist_ids.add(cached.artist_id)
            else:
                songs_needing_artist_embed.append(song.spotify_id)

    def _embed_song_artist_id(track_id: str) -> str | None:
        try:
            track = fetch_track_details_from_embed(track_id)
        except SpotifyError:
            return None
        return track.artist_id or None

    for artist_id in map_parallel(
        songs_needing_artist_embed,
        _embed_song_artist_id,
        max_workers=EMBED_PARALLEL_WORKERS,
    ):
        if artist_id:
            resolved_artist_ids.add(artist_id)

    song_artist_ids = resolved_artist_ids | {
        s.artist_id for s in liked_songs + disliked_songs if s.artist_id
    }

    if web_api:
        for artist in liked_artists[:5]:
            if not artist.spotify_id or not is_spotify_catalog_id(artist.spotify_id):
                continue
            related = get_related_artist_ids(artist.spotify_id, config=config)
            candidate_artist_ids.update(related[:10])

        for artist_id in list(resolved_artist_ids)[:8]:
            related = get_related_artist_ids(artist_id, config=config)
            candidate_artist_ids.update(related[:8])

    candidate_artist_ids -= taste_artist_ids_all
    candidate_artist_ids -= song_artist_ids

    seed_artist_ids = resolved_artist_ids | {
        a.spotify_id
        for a in liked_artists + disliked_artists
        if a.spotify_id and is_spotify_catalog_id(a.spotify_id)
    }

    collaborator_counts: dict[str, int] = {}

    # Fallback: when the related-artist Web API is 403-blocked, discover collaborators
    # credited on the user's liked songs and collab top-tracks from embed pages.
    if not candidate_artist_ids:
        if not embed_track_cache:
            embed_track_cache = collect_embed_recommendation_tracks(
                liked_songs,
                liked_artists,
            )

        artists_in_cache = {t.artist_id for t in embed_track_cache.values() if t.artist_id}
        missing_top_track_artists = [
            artist_id
            for artist_id in list(resolved_artist_ids)[:20]
            if artist_id not in artists_in_cache
        ]

        def _fetch_collab_tracks(artist_id: str) -> list[TrackDetails]:
            try:
                return fetch_artist_top_tracks_from_embed(artist_id)
            except SpotifyError:
                return []

        for tracks in map_parallel(
            missing_top_track_artists,
            _fetch_collab_tracks,
            max_workers=EMBED_PARALLEL_WORKERS,
        ):
            if not tracks:
                continue
            for track in tracks:
                embed_track_cache[track.spotify_id] = track

        collaborator_counts = collect_collaborator_artist_candidates(
            liked_songs,
            embed_track_cache,
            seed_artist_ids,
        )
        candidate_artist_ids.update(collaborator_counts.keys())
        candidate_artist_ids -= taste_artist_ids_all
        candidate_artist_ids -= seed_artist_ids

    # Count how many embed cache tracks belong to each candidate (relatedness proxy)
    embed_artist_track_counts: dict[str, int] = {}
    for track in embed_track_cache.values():
        if track.artist_id:
            embed_artist_track_counts[track.artist_id] = (
                embed_artist_track_counts.get(track.artist_id, 0) + 1
            )

    artist_related_map: dict[str, list[str]] = {}
    candidate_list = sorted(candidate_artist_ids)[:40]
    if web_api:
        for candidate_id in candidate_list:
            artist_related_map[candidate_id] = get_related_artist_ids(candidate_id, config=config)

    liked_artist_name_list = [a.name for a in liked_artists]
    liked_song_artist_list = [s.artist for s in liked_songs]

    def _fetch_artist_details(candidate_id: str) -> ArtistDetails | None:
        try:
            return get_artist_details_with_fallback(candidate_id, config=config)
        except SpotifyError:
            return None

    artist_details_cache: dict[str, ArtistDetails] = {}
    for candidate_id, details in zip(
        candidate_list,
        map_parallel(candidate_list, _fetch_artist_details),
    ):
        if details is not None:
            artist_details_cache[candidate_id] = details

    scored_artists: list[ArtistRecommendation] = []
    seen_artist_ids: set[str] = set()
    for candidate_id in candidate_list:
        if candidate_id in seen_artist_ids:
            continue
        seen_artist_ids.add(candidate_id)
        details = artist_details_cache.get(candidate_id)
        if details is None:
            continue
        genres = _resolve_item_genres(
            artist_id=details.spotify_id,
            artist_name=details.name,
            existing_genres=details.genres,
            config=config,
            liked_artists=liked_artists,
            cache=genre_cache,
        )
        details = _artist_with_genres(details, genres)
        if _artist_is_liked(details, liked_artists):
            continue
        if explicit_genres:
            if not details.genres:
                continue
            if not any(
                g.lower() in {fg.lower() for fg in explicit_genres} for g in details.genres
            ):
                continue
        related_ids = artist_related_map.get(candidate_id, [])
        related_liked_count = len(set(related_ids) & liked_artist_ids)
        scr = artist_score(
            candidate_genres=details.genres,
            candidate_spotify_id=details.spotify_id,
            candidate_popularity=details.popularity,
            candidate_related_ids=related_ids,
            liked_genres=liked_genres,
            disliked_genres=disliked_genres,
            liked_artist_ids=liked_artist_ids,
            year_min=filters.year_min,
            year_max=filters.year_max,
            weights=weights,
            embed_liked_song_count=embed_artist_track_counts.get(candidate_id, 0),
            collab_liked_song_count=collaborator_counts.get(candidate_id, 0),
            taste_name_match=artist_taste_text_match(
                details.name,
                liked_artist_name_list,
                liked_song_artist_list,
            ),
        )
        reason = artist_reason(
            candidate_name=details.name,
            candidate_genres=details.genres,
            candidate_popularity=details.popularity,
            score=scr,
            liked_genres=liked_genres,
            liked_artist_names={a.name for a in liked_artists},
            related_liked_count=related_liked_count,
        )
        scored_artists.append(
            ArtistRecommendation(
                artist=details,
                related_liked_count=related_liked_count,
                score=scr,
                reason=reason,
            )
        )

    scored_artists.sort(key=lambda x: x.score.total, reverse=True)
    top_artists = scored_artists[: filters.artist_count]

    return top_songs, top_artists
