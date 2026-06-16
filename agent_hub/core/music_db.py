from __future__ import annotations

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
    spotify_id TEXT UNIQUE NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_taste_artists_spotify_id ON taste_artists(spotify_id);

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


def init_db(config: HubConfig | None = None) -> Path:
    path = music_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
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
