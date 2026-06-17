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


def test_schema_tables(music_config):
    import sqlite3

    path = init_db(music_config)
    conn = sqlite3.connect(path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "taste_songs" in tables
    assert "taste_artists" in tables
    assert "taste_artist_top_tracks" in tables
    assert "wishlist_songs" in tables
    assert "wishlist_artists" in tables
