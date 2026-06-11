from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from agent_hub.core.config import HubConfig, load_config


def movie_data_dir(config: HubConfig | None = None) -> Path:
    config = config or load_config()
    return config.data_dir / "movies"


def movie_db_path(config: HubConfig | None = None) -> Path:
    return movie_data_dir(config) / "movies.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS taste_movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tmdb_id INTEGER UNIQUE NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    genres TEXT,
    director TEXT,
    cast TEXT,
    keywords TEXT,
    rating REAL,
    runtime INTEGER,
    poster_url TEXT,
    overview TEXT,
    imdb_id TEXT,
    imdb_rating TEXT,
    rotten_tomatoes_score TEXT,
    metacritic_score TEXT,
    sentiment TEXT NOT NULL CHECK(sentiment IN ('like', 'dislike')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_taste_sentiment ON taste_movies(sentiment);
CREATE INDEX IF NOT EXISTS idx_taste_tmdb_id ON taste_movies(tmdb_id);

CREATE TABLE IF NOT EXISTS wishlist_movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tmdb_id INTEGER UNIQUE NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    genres TEXT,
    director TEXT,
    cast TEXT,
    keywords TEXT,
    rating REAL,
    runtime INTEGER,
    poster_url TEXT,
    overview TEXT,
    imdb_id TEXT,
    imdb_rating TEXT,
    rotten_tomatoes_score TEXT,
    metacritic_score TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wishlist_tmdb_id ON wishlist_movies(tmdb_id);
"""


def _migrate_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(taste_movies)").fetchall()}
    if "imdb_id" not in columns:
        conn.execute("ALTER TABLE taste_movies ADD COLUMN imdb_id TEXT")
    if "rotten_tomatoes_score" not in columns:
        conn.execute("ALTER TABLE taste_movies ADD COLUMN rotten_tomatoes_score TEXT")
    if "imdb_rating" not in columns:
        conn.execute("ALTER TABLE taste_movies ADD COLUMN imdb_rating TEXT")
    if "metacritic_score" not in columns:
        conn.execute("ALTER TABLE taste_movies ADD COLUMN metacritic_score TEXT")


def init_db(config: HubConfig | None = None) -> Path:
    path = movie_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_schema(conn)
    return path


@contextmanager
def connect(db_path: Path | None = None, config: HubConfig | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or movie_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
