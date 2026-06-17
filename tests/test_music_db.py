from pathlib import Path

import pytest

from agent_hub.core.config import HubConfig, SpotifyConfig
from agent_hub.core.music_db import init_db, music_db_path


@pytest.fixture
def music_config(tmp_path: Path) -> HubConfig:
    return HubConfig(
        data_dir=tmp_path,
        spotify=SpotifyConfig(client_id="test-id", client_secret="test-secret"),
    )


def test_init_db_creates_file(music_config):
    path = init_db(music_config)
    assert path.exists()
    assert path.suffix == ".db"


def test_db_path(music_config):
    path = music_db_path(music_config)
    assert path.parent.name == "music"
    assert path.name == "music.db"


def test_init_db_migrates_legacy_taste_artists(music_config):
    import sqlite3

    from agent_hub.core.music_db import connect, init_db, music_db_path

    path = music_db_path(music_config)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE taste_artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spotify_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            genres TEXT,
            popularity INTEGER,
            followers INTEGER,
            image_url TEXT,
            sentiment TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO taste_artists
        (spotify_id, name, genres, popularity, followers, image_url, sentiment, created_at, updated_at)
        VALUES ('pandora-artist-legacy1', 'Legacy Artist', '[]', 0, 0, NULL, 'like', 't', 't');
        """
    )
    conn.commit()
    conn.close()

    init_db(music_config)
    with connect(config=music_config) as conn:
        row = conn.execute("SELECT pandora_id, spotify_id FROM taste_artists").fetchone()
    assert row["pandora_id"] == "pandora-artist-legacy1"
    assert row["spotify_id"] is None


def test_schema_tables(music_config):
    import sqlite3

    path = init_db(music_config)
    conn = sqlite3.connect(path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    columns = {row[1] for row in conn.execute("PRAGMA table_info(taste_artists)")}
    conn.close()
    assert "taste_songs" in tables
    assert "taste_artists" in tables
    assert "taste_artist_top_tracks" in tables
    assert "wishlist_songs" in tables
    assert "wishlist_artists" in tables
    assert "pandora_id" in columns
    assert "spotify_id" in columns
