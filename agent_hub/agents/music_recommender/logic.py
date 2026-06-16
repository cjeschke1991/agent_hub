from __future__ import annotations

import json
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
    song_score,
)
from agent_hub.agents.music_recommender.spotify import (
    ArtistDetails,
    SpotifyConfigError,
    SpotifyError,
    TrackDetails,
    fetch_playlist_tracks_from_embed,
    get_available_genre_seeds,
    get_artist_details,
    get_artist_top_track_ids,
    get_related_artist_ids,
    get_spotify_recommendations,
    get_track_details,
    search_artists,
    search_tracks,
    search_tracks_by_genre,
    spotify_configured,
)
from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.music_db import connect, init_db
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
    spotify_id: str
    name: str
    genres: list[str]
    popularity: int
    followers: int
    image_url: str | None
    sentiment: str
    created_at: str
    updated_at: str


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
    return TasteArtist(
        id=int(row["id"]),
        spotify_id=str(row["spotify_id"]),
        name=str(row["name"]),
        genres=_parse_json_list(row["genres"]),
        popularity=int(row["popularity"] or 0),
        followers=int(row["followers"] or 0),
        image_url=row["image_url"],
        sentiment=str(row["sentiment"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


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
    now = utc_now_iso()
    with connect(config=config) as conn:
        existing = conn.execute(
            "SELECT id FROM taste_artists WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE taste_artists
                SET name=?, genres=?, popularity=?, followers=?, image_url=?, sentiment=?, updated_at=?
                WHERE spotify_id=?
                """,
                (
                    details.name, _json_dumps(details.genres), details.popularity,
                    details.followers, details.image_url, sentiment, now, details.spotify_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO taste_artists
                (spotify_id, name, genres, popularity, followers, image_url, sentiment, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    details.spotify_id, details.name, _json_dumps(details.genres),
                    details.popularity, details.followers, details.image_url, sentiment, now, now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM taste_artists WHERE spotify_id = ?", (details.spotify_id,)
        ).fetchone()
    return _row_to_taste_artist(row)


def add_song(spotify_id: str, sentiment: str, config: HubConfig | None = None) -> TasteSong:
    details = get_track_details(spotify_id, config=config)
    return _upsert_taste_song(details, sentiment, config=config)


def add_artist(spotify_id: str, sentiment: str, config: HubConfig | None = None) -> TasteArtist:
    details = get_artist_details(spotify_id, config=config)
    return _upsert_taste_artist(details, sentiment, config=config)


def remove_song(spotify_id: str, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute("DELETE FROM taste_songs WHERE spotify_id = ?", (spotify_id,))


def remove_artist(spotify_id: str, config: HubConfig | None = None) -> None:
    ensure_db(config)
    with connect(config=config) as conn:
        conn.execute("DELETE FROM taste_artists WHERE spotify_id = ?", (spotify_id,))


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
    """Return Spotify recommendation genre seeds for UI filters."""
    if not spotify_configured(config):
        raise SpotifyConfigError("Spotify is not configured.")
    return get_available_genre_seeds(config=config)


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
    liked_artist_ids.update(a.spotify_id for a in liked_artists)

    disliked_artist_ids = {s.artist_id for s in disliked_songs if s.artist_id}
    disliked_artist_ids.update(a.spotify_id for a in disliked_artists)

    liked_years = [s.year for s in liked_songs if s.year is not None]

    return (
        liked_genres, disliked_genres,
        liked_energy, liked_valence, liked_danceability,
        liked_artist_ids, disliked_artist_ids,
        liked_years,
    )


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

    weights = config.music_recommender.weights
    explicit_genres = filters.genre_names or []
    search_genres = explicit_genres or sorted(liked_genres)[:3]

    # --- Song candidates ---
    candidate_track_ids: set[str] = set()

    # Spotify recs (may be unavailable for newer apps)
    seed_track_ids = [s.spotify_id for s in liked_songs[:2]]
    seed_artist_ids = [a.spotify_id for a in liked_artists[:3]]
    recs = get_spotify_recommendations(
        seed_track_ids=seed_track_ids or None,
        seed_artist_ids=seed_artist_ids or None,
        seed_genres=explicit_genres[:5] if explicit_genres else None,
        energy_min=filters.energy_min if filters.energy_min > 0 else None,
        energy_max=filters.energy_max if filters.energy_max < 1 else None,
        valence_min=filters.valence_min if filters.valence_min > 0 else None,
        valence_max=filters.valence_max if filters.valence_max < 1 else None,
        limit=50,
        config=config,
    )
    candidate_track_ids.update(recs)

    # Top tracks from liked artists
    for artist in liked_artists[:5]:
        top = get_artist_top_track_ids(artist.spotify_id, config=config)
        candidate_track_ids.update(top[:5])
    for song in liked_songs[:3]:
        if song.artist_id:
            top = get_artist_top_track_ids(song.artist_id, config=config)
            candidate_track_ids.update(top[:3])

    # Genre search fallback
    for genre in search_genres[:3]:
        ids = search_tracks_by_genre(genre, limit=10, config=config)
        candidate_track_ids.update(ids)

    # Remove already-rated tracks
    candidate_track_ids -= taste_spotify_ids

    # Fetch details and score
    scored_songs: list[SongRecommendation] = []
    seen_track_ids: set[str] = set()
    for track_id in list(candidate_track_ids)[:80]:
        if track_id in seen_track_ids:
            continue
        seen_track_ids.add(track_id)
        try:
            details = get_track_details(track_id, config=config)
        except SpotifyError:
            continue
        if details.year is not None and (
            details.year < filters.year_min or details.year > filters.year_max
        ):
            continue
        if explicit_genres:
            if not any(
                g.lower() in {fg.lower() for fg in explicit_genres} for g in details.genres
            ):
                continue
        elif search_genres and not any(
            g.lower() in {fg.lower() for fg in search_genres} for g in details.genres
        ):
            if liked_genres and not any(g.lower() in liked_genres for g in details.genres):
                continue
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
            liked_artist_names={a.name for a in liked_artists},
            candidate_artist_in_liked=details.artist_id in liked_artist_ids,
        )
        scored_songs.append(SongRecommendation(track=details, score=scr, reason=reason))

    scored_songs.sort(key=lambda x: x.score.total, reverse=True)
    top_songs = scored_songs[: filters.song_count]

    # --- Artist candidates ---
    candidate_artist_ids: set[str] = set()
    taste_artist_ids_all = {a.spotify_id for a in liked_artists + disliked_artists}
    song_artist_ids = {s.artist_id for s in liked_songs + disliked_songs if s.artist_id}

    for artist in liked_artists[:5]:
        related = get_related_artist_ids(artist.spotify_id, config=config)
        candidate_artist_ids.update(related[:10])

    candidate_artist_ids -= taste_artist_ids_all
    candidate_artist_ids -= song_artist_ids

    artist_related_map: dict[str, list[str]] = {}
    for candidate_id in list(candidate_artist_ids)[:40]:
        related = get_related_artist_ids(candidate_id, config=config)
        artist_related_map[candidate_id] = related

    scored_artists: list[ArtistRecommendation] = []
    seen_artist_ids: set[str] = set()
    for candidate_id in list(candidate_artist_ids)[:40]:
        if candidate_id in seen_artist_ids:
            continue
        seen_artist_ids.add(candidate_id)
        try:
            details = get_artist_details(candidate_id, config=config)
        except SpotifyError:
            continue
        if explicit_genres and not any(
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
