from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_hub.core.paths import PROJECT_ROOT, resolve_data_dir


@dataclass
class BriefingConfig:
    title: str = "Daily Briefing"


@dataclass
class TmdbConfig:
    api_key: str = ""


@dataclass
class OmdbConfig:
    api_key: str = ""


@dataclass
class MovieRecommenderWeights:
    genre: float = 0.35
    cast_director: float = 0.25
    year: float = 0.15
    rating: float = 0.15
    keywords: float = 0.10


@dataclass
class MovieRecommenderConfig:
    weights: MovieRecommenderWeights = field(default_factory=MovieRecommenderWeights)


@dataclass
class HubConfig:
    data_dir: Path
    slice_order: list[str] = field(default_factory=list)
    stale_hours: dict[str, Any] = field(default_factory=dict)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)
    tmdb: TmdbConfig = field(default_factory=TmdbConfig)
    omdb: OmdbConfig = field(default_factory=OmdbConfig)
    movie_recommender: MovieRecommenderConfig = field(default_factory=MovieRecommenderConfig)

    def stale_threshold_hours(self, agent_id: str) -> float:
        default = self.stale_hours.get("default", 36)
        return float(self.stale_hours.get(agent_id, default))


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.environ.get(key, "").strip():
            os.environ[key] = value


def load_config(config_path: Path | None = None) -> HubConfig:
    _load_dotenv()
    path = config_path or (PROJECT_ROOT / "config.yaml")
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

    briefing_raw = raw.get("briefing", {}) or {}
    tmdb_raw = raw.get("tmdb", {}) or {}
    omdb_raw = raw.get("omdb", {}) or {}
    movie_raw = raw.get("movie_recommender", {}) or {}
    weights_raw = movie_raw.get("weights", {}) or {}

    api_key = os.environ.get("TMDB_API_KEY") or str(tmdb_raw.get("api_key", "") or "")
    omdb_api_key = os.environ.get("OMDB_API_KEY") or str(omdb_raw.get("api_key", "") or "")

    return HubConfig(
        data_dir=resolve_data_dir(raw.get("data_dir", "data")),
        slice_order=list(raw.get("slice_order", [])),
        stale_hours=dict(raw.get("stale_hours", {})),
        briefing=BriefingConfig(title=briefing_raw.get("title", "Daily Briefing")),
        tmdb=TmdbConfig(api_key=api_key.strip()),
        omdb=OmdbConfig(api_key=omdb_api_key.strip()),
        movie_recommender=MovieRecommenderConfig(
            weights=MovieRecommenderWeights(
                genre=float(weights_raw.get("genre", 0.35)),
                cast_director=float(weights_raw.get("cast_director", 0.25)),
                year=float(weights_raw.get("year", 0.15)),
                rating=float(weights_raw.get("rating", 0.15)),
                keywords=float(weights_raw.get("keywords", 0.10)),
            )
        ),
    )
