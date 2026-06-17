from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from agent_hub.core.config import HubConfig, load_config


def music_data_dir(config: HubConfig | None = None) -> Path:
    config = config or load_config()
    return config.data_dir / "music"


def music_db_path(config: HubConfig | None = None) -> Path:
    return music_data_dir(config) / "music.db"


def pandora_artist_id(artist_name: str) -> str:
    digest = hashlib.sha1(artist_name.lower().encode()).hexdigest()[:16]
    return f"pandora-artist-{digest}"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS taste_songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    artist_id TEXT,
    album TEXT,
    year INTEGER,
    genres TEXT,
    energy REAL,
    valence REAL,
    danceability REAL,
    tempo REAL,
    popularity INTEGER,
    duration_ms INTEGER,
    image_url TEXT,
    preview_url TEXT,
    sentiment TEXT NOT NULL CHECK(sentiment IN ('like', 'dislike')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_taste_songs_sentiment ON taste_songs(sentiment);
CREATE INDEX IF NOT EXISTS idx_taste_songs_spotify_id ON taste_songs(spotify_id);

CREATE TABLE IF NOT EXISTS taste_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pandora_id TEXT UNIQUE NOT NULL,
    spotify_id TEXT,
    name TEXT NOT NULL,
    genres TEXT,
    popularity INTEGER,
    followers INTEGER,
    image_url TEXT,
    sentiment TEXT NOT NULL CHECK(sentiment IN ('like', 'dislike')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_taste_artists_sentiment ON taste_artists(sentiment);
CREATE INDEX IF NOT EXISTS idx_taste_artists_pandora_id ON taste_artists(pandora_id);
CREATE INDEX IF NOT EXISTS idx_taste_artists_spotify_id ON taste_artists(spotify_id);

CREATE TABLE IF NOT EXISTS taste_artist_top_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_pandora_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    track_spotify_id TEXT NOT NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT,
    year INTEGER,
    image_url TEXT,
    preview_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(artist_pandora_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_taste_artist_top_tracks_artist
    ON taste_artist_top_tracks(artist_pandora_id);

CREATE TABLE IF NOT EXISTS wishlist_songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    artist_id TEXT,
    album TEXT,
    year INTEGER,
    genres TEXT,
    energy REAL,
    valence REAL,
    danceability REAL,
    tempo REAL,
    popularity INTEGER,
    duration_ms INTEGER,
    image_url TEXT,
    preview_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wishlist_songs_spotify_id ON wishlist_songs(spotify_id);

CREATE TABLE IF NOT EXISTS wishlist_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    genres TEXT,
    popularity INTEGER,
    followers INTEGER,
    image_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wishlist_artists_spotify_id ON wishlist_artists(spotify_id);
"""


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_taste_artists_dual_ids(conn: sqlite3.Connection) -> None:
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "taste_artists" not in tables:
        return

    columns = _table_columns(conn, "taste_artists")
    if "pandora_id" in columns:
        return

    conn.execute("ALTER TABLE taste_artists ADD COLUMN pandora_id TEXT")
    for row in conn.execute("SELECT id, spotify_id, name FROM taste_artists"):
        spotify_id = str(row["spotify_id"])
        name = str(row["name"])
        if spotify_id.startswith("pandora-"):
            pandora_id = spotify_id
        else:
            pandora_id = pandora_artist_id(name)
        conn.execute(
            "UPDATE taste_artists SET pandora_id = ? WHERE id = ?",
            (pandora_id, row["id"]),
        )

    conn.executescript(
        """
        CREATE TABLE taste_artists_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pandora_id TEXT UNIQUE NOT NULL,
            spotify_id TEXT,
            name TEXT NOT NULL,
            genres TEXT,
            popularity INTEGER,
            followers INTEGER,
            image_url TEXT,
            sentiment TEXT NOT NULL CHECK(sentiment IN ('like', 'dislike')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        INSERT INTO taste_artists_new (
            id, pandora_id, spotify_id, name, genres, popularity, followers, image_url,
            sentiment, created_at, updated_at
        )
        SELECT
            id,
            pandora_id,
            CASE WHEN spotify_id LIKE 'pandora-%' THEN NULL ELSE spotify_id END,
            name, genres, popularity, followers, image_url, sentiment, created_at, updated_at
        FROM taste_artists;

        DROP TABLE taste_artists;
        ALTER TABLE taste_artists_new RENAME TO taste_artists;

        CREATE INDEX IF NOT EXISTS idx_taste_artists_sentiment ON taste_artists(sentiment);
        CREATE INDEX IF NOT EXISTS idx_taste_artists_pandora_id ON taste_artists(pandora_id);
        CREATE INDEX IF NOT EXISTS idx_taste_artists_spotify_id ON taste_artists(spotify_id);
        """
    )


def _migrate_taste_artist_top_tracks(conn: sqlite3.Connection) -> None:
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "taste_artist_top_tracks" not in tables:
        return

    columns = _table_columns(conn, "taste_artist_top_tracks")
    if "artist_pandora_id" in columns:
        return
    if "artist_spotify_id" not in columns:
        return

    conn.executescript(
        """
        CREATE TABLE taste_artist_top_tracks_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_pandora_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            track_spotify_id TEXT NOT NULL,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            album TEXT,
            year INTEGER,
            image_url TEXT,
            preview_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(artist_pandora_id, rank)
        );
        """
    )
    rows = conn.execute("SELECT * FROM taste_artist_top_tracks").fetchall()
    for row in rows:
        artist_key = str(row["artist_spotify_id"])
        pandora_row = conn.execute(
            """
            SELECT pandora_id FROM taste_artists
            WHERE pandora_id = ? OR spotify_id = ?
            LIMIT 1
            """,
            (artist_key, artist_key),
        ).fetchone()
        artist_pandora_id = str(pandora_row["pandora_id"]) if pandora_row else artist_key
        conn.execute(
            """
            INSERT INTO taste_artist_top_tracks_new
            (artist_pandora_id, rank, track_spotify_id, title, artist, album, year,
             image_url, preview_url, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                artist_pandora_id,
                row["rank"],
                row["track_spotify_id"],
                row["title"],
                row["artist"],
                row["album"],
                row["year"],
                row["image_url"],
                row["preview_url"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    conn.executescript(
        """
        DROP TABLE taste_artist_top_tracks;
        ALTER TABLE taste_artist_top_tracks_new RENAME TO taste_artist_top_tracks;
        CREATE INDEX IF NOT EXISTS idx_taste_artist_top_tracks_artist
            ON taste_artist_top_tracks(artist_pandora_id);
        """
    )


def _migrate_taste_artists_shared_spotify_id(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='taste_artists'"
    ).fetchone()
    if not row or not row[0]:
        return
    if "spotify_id TEXT UNIQUE" not in row[0]:
        return

    conn.executescript(
        """
        CREATE TABLE taste_artists_shared (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pandora_id TEXT UNIQUE NOT NULL,
            spotify_id TEXT,
            name TEXT NOT NULL,
            genres TEXT,
            popularity INTEGER,
            followers INTEGER,
            image_url TEXT,
            sentiment TEXT NOT NULL CHECK(sentiment IN ('like', 'dislike')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        INSERT INTO taste_artists_shared (
            id, pandora_id, spotify_id, name, genres, popularity, followers, image_url,
            sentiment, created_at, updated_at
        )
        SELECT
            id, pandora_id, spotify_id, name, genres, popularity, followers, image_url,
            sentiment, created_at, updated_at
        FROM taste_artists;

        DROP TABLE taste_artists;
        ALTER TABLE taste_artists_shared RENAME TO taste_artists;

        CREATE INDEX IF NOT EXISTS idx_taste_artists_sentiment ON taste_artists(sentiment);
        CREATE INDEX IF NOT EXISTS idx_taste_artists_pandora_id ON taste_artists(pandora_id);
        CREATE INDEX IF NOT EXISTS idx_taste_artists_spotify_id ON taste_artists(spotify_id);
        """
    )


def _run_migrations(conn: sqlite3.Connection) -> None:
    _migrate_taste_artists_dual_ids(conn)
    _migrate_taste_artist_top_tracks(conn)
    _migrate_taste_artists_shared_spotify_id(conn)


def init_db(config: HubConfig | None = None) -> Path:
    path = music_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        if path.exists():
            _run_migrations(conn)
        conn.executescript(SCHEMA_SQL)
        _run_migrations(conn)
    return path


@contextmanager
def connect(db_path: Path | None = None, config: HubConfig | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or music_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
