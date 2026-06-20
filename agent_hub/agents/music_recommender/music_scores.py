"""User-assigned 0-10 ratings for songs and artists.

Scores are stored alongside rich context (title, artist, genres, AI score) in
a JSON file.  Ratings influence recommendations via post-score multipliers on
candidates and weighted taste-profile signals for liked library items.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_hub.core.config import HubConfig, load_config


def _scores_path(config: HubConfig) -> Path:
    return Path(config.data_dir) / "music_user_scores.json"


def _load_raw(config: HubConfig) -> dict[str, Any]:
    path = _scores_path(config)
    if not path.exists():
        return {"songs": {}, "artists": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"songs": {}, "artists": {}}


def _save_raw(data: dict[str, Any], config: HubConfig) -> None:
    path = _scores_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save_song_score(
    spotify_id: str,
    score: int,
    *,
    title: str = "",
    artist: str = "",
    genres: list[str] | None = None,
    ai_score: float | None = None,
    config: HubConfig | None = None,
) -> None:
    cfg = config or load_config()
    data = _load_raw(cfg)
    data["songs"][spotify_id] = {
        "score": int(score),
        "title": title,
        "artist": artist,
        "genres": genres or [],
        "ai_score": ai_score,
    }
    _save_raw(data, cfg)


def save_artist_score(
    spotify_id: str,
    score: int,
    *,
    name: str = "",
    genres: list[str] | None = None,
    ai_score: float | None = None,
    config: HubConfig | None = None,
) -> None:
    cfg = config or load_config()
    data = _load_raw(cfg)
    data["artists"][spotify_id] = {
        "score": int(score),
        "name": name,
        "genres": genres or [],
        "ai_score": ai_score,
    }
    _save_raw(data, cfg)


def load_song_score(spotify_id: str, config: HubConfig | None = None) -> int | None:
    cfg = config or load_config()
    entry = _load_raw(cfg)["songs"].get(spotify_id)
    return int(entry["score"]) if entry and "score" in entry else None


def load_artist_score(spotify_id: str, config: HubConfig | None = None) -> int | None:
    cfg = config or load_config()
    entry = _load_raw(cfg)["artists"].get(spotify_id)
    return int(entry["score"]) if entry and "score" in entry else None


def load_all_song_scores(config: HubConfig | None = None) -> dict[str, int]:
    """Return {spotify_id: score} for every rated song."""
    cfg = config or load_config()
    return {
        sid: int(e["score"])
        for sid, e in _load_raw(cfg)["songs"].items()
        if "score" in e
    }


def load_all_artist_scores(config: HubConfig | None = None) -> dict[str, int]:
    """Return {spotify_id: score} for every rated artist."""
    cfg = config or load_config()
    return {
        aid: int(e["score"])
        for aid, e in _load_raw(cfg)["artists"].items()
        if "score" in e
    }


# ---------------------------------------------------------------------------
# Algorithm integration
# ---------------------------------------------------------------------------

def artist_score_key(spotify_id: str | None, *, pandora_id: str | None = None) -> str:
    """Stable storage key for an artist (Spotify ID preferred)."""
    if spotify_id:
        return spotify_id
    if pandora_id:
        return f"pandora:{pandora_id}"
    return ""


def user_score_multiplier(score: int) -> float:
    """Convert a 0-10 user rating into a score.total multiplier.

    8-10 → 1.15 boost   (user loves it)
    5-7  → 1.00 neutral
    0-4  → 0.75 penalty (user dislikes it)
    """
    if score >= 8:
        return 1.15
    if score >= 5:
        return 1.0
    return 0.75


def taste_profile_weight(score: int | None) -> float:
    """Weight liked-item signals in taste profile (0.5 at score 0 .. 1.5 at 10)."""
    if score is None:
        return 1.0
    return 0.5 + score / 10.0


def resolve_candidate_multiplier(
    track_id: str | None,
    artist_id: str | None,
    song_scores: dict[str, int],
    artist_scores: dict[str, int],
) -> float:
    """Multiplier for a recommendation candidate from direct or artist ratings."""
    if track_id and track_id in song_scores:
        return user_score_multiplier(song_scores[track_id])
    if artist_id and artist_id in artist_scores:
        return user_score_multiplier(artist_scores[artist_id])
    return 1.0
