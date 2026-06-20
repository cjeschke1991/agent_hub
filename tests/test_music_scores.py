"""Tests for music_scores — save/load/multiplier."""
from __future__ import annotations

import pytest

from agent_hub.agents.music_recommender.music_scores import (
    load_all_artist_scores,
    load_all_song_scores,
    load_artist_score,
    load_song_score,
    save_artist_score,
    save_song_score,
    user_score_multiplier,
)
from agent_hub.core.config import HubConfig


@pytest.fixture()
def cfg(tmp_path):
    return HubConfig(data_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# user_score_multiplier
# ---------------------------------------------------------------------------

def test_multiplier_high():
    assert user_score_multiplier(10) == 1.15
    assert user_score_multiplier(8) == 1.15


def test_multiplier_mid():
    assert user_score_multiplier(7) == 1.0
    assert user_score_multiplier(5) == 1.0


def test_multiplier_low():
    assert user_score_multiplier(4) == 0.75
    assert user_score_multiplier(0) == 0.75


# ---------------------------------------------------------------------------
# Song scores
# ---------------------------------------------------------------------------

def test_save_load_song_score(cfg):
    assert load_song_score("track1", config=cfg) is None
    save_song_score("track1", 7, title="My Song", artist="Artist A", config=cfg)
    assert load_song_score("track1", config=cfg) == 7


def test_overwrite_song_score(cfg):
    save_song_score("track1", 5, config=cfg)
    save_song_score("track1", 9, config=cfg)
    assert load_song_score("track1", config=cfg) == 9


def test_load_all_song_scores(cfg):
    save_song_score("t1", 3, config=cfg)
    save_song_score("t2", 8, config=cfg)
    all_scores = load_all_song_scores(cfg)
    assert all_scores == {"t1": 3, "t2": 8}


# ---------------------------------------------------------------------------
# Artist scores
# ---------------------------------------------------------------------------

def test_save_load_artist_score(cfg):
    assert load_artist_score("artist1", config=cfg) is None
    save_artist_score("artist1", 6, name="Cool Artist", genres=["pop"], config=cfg)
    assert load_artist_score("artist1", config=cfg) == 6


def test_overwrite_artist_score(cfg):
    save_artist_score("artist1", 2, config=cfg)
    save_artist_score("artist1", 10, config=cfg)
    assert load_artist_score("artist1", config=cfg) == 10


def test_load_all_artist_scores(cfg):
    save_artist_score("a1", 1, config=cfg)
    save_artist_score("a2", 9, config=cfg)
    all_scores = load_all_artist_scores(cfg)
    assert all_scores == {"a1": 1, "a2": 9}


# ---------------------------------------------------------------------------
# Song and artist scores are independent namespaces
# ---------------------------------------------------------------------------

def test_song_artist_namespaces_are_independent(cfg):
    save_song_score("shared_id", 3, config=cfg)
    save_artist_score("shared_id", 8, config=cfg)
    assert load_song_score("shared_id", config=cfg) == 3
    assert load_artist_score("shared_id", config=cfg) == 8


# ---------------------------------------------------------------------------
# Metadata persisted alongside score
# ---------------------------------------------------------------------------

def test_song_metadata_persisted(cfg, tmp_path):
    import json
    save_song_score(
        "tid",
        7,
        title="Title",
        artist="Artist",
        genres=["rock"],
        ai_score=82.5,
        config=cfg,
    )
    raw = json.loads((tmp_path / "music_user_scores.json").read_text())
    entry = raw["songs"]["tid"]
    assert entry["title"] == "Title"
    assert entry["artist"] == "Artist"
    assert entry["genres"] == ["rock"]
    assert entry["ai_score"] == 82.5
    assert entry["score"] == 7
