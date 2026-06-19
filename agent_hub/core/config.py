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
class SpotifyConfig:
    client_id: str = ""
    client_secret: str = ""


@dataclass
class MusicRecommenderWeights:
    song_genre: float = 0.30
    song_audio_features: float = 0.25
    song_artist_affinity: float = 0.20
    song_year: float = 0.15
    song_popularity: float = 0.10
    artist_genre: float = 0.40
    artist_related_artists: float = 0.25
    artist_popularity: float = 0.20
    artist_era: float = 0.15


@dataclass
class MusicZoneWeights:
    """Per-zone scoring weights for the three discovery zones."""
    song_genre: float
    song_audio_features: float
    song_artist_affinity: float
    song_year: float
    song_popularity: float  # negative = anti-popularity bias


@dataclass
class MusicZoneConfig:
    safe: MusicZoneWeights = field(default_factory=lambda: MusicZoneWeights(
        song_genre=0.20,
        song_audio_features=0.25,
        song_artist_affinity=0.35,
        song_year=0.10,
        song_popularity=0.10,
    ))
    stretch: MusicZoneWeights = field(default_factory=lambda: MusicZoneWeights(
        song_genre=0.45,
        song_audio_features=0.30,
        song_artist_affinity=0.00,
        song_year=0.10,
        song_popularity=0.15,
    ))
    wild_card: MusicZoneWeights = field(default_factory=lambda: MusicZoneWeights(
        song_genre=0.20,
        song_audio_features=0.25,
        song_artist_affinity=0.00,
        song_year=0.05,
        song_popularity=-0.15,
    ))


@dataclass
class MusicRecommenderConfig:
    weights: MusicRecommenderWeights = field(default_factory=MusicRecommenderWeights)
    zones: MusicZoneConfig = field(default_factory=MusicZoneConfig)


@dataclass
class GmailConfig:
    credentials_path: str = ""
    max_emails: int = 50
    token_path: str = ""  # defaults to ~/.agent_hub/gmail_token.json if empty


@dataclass
class HubConfig:
    data_dir: Path
    slice_order: list[str] = field(default_factory=list)
    stale_hours: dict[str, Any] = field(default_factory=dict)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)
    tmdb: TmdbConfig = field(default_factory=TmdbConfig)
    omdb: OmdbConfig = field(default_factory=OmdbConfig)
    movie_recommender: MovieRecommenderConfig = field(default_factory=MovieRecommenderConfig)
    spotify: SpotifyConfig = field(default_factory=SpotifyConfig)
    music_recommender: MusicRecommenderConfig = field(default_factory=MusicRecommenderConfig)
    gmail: GmailConfig = field(default_factory=GmailConfig)

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


def _load_zone_weights(raw: dict[str, Any], default: "MusicZoneWeights") -> "MusicZoneWeights":
    if not raw:
        return default
    return MusicZoneWeights(
        song_genre=float(raw.get("song_genre", default.song_genre)),
        song_audio_features=float(raw.get("song_audio_features", default.song_audio_features)),
        song_artist_affinity=float(raw.get("song_artist_affinity", default.song_artist_affinity)),
        song_year=float(raw.get("song_year", default.song_year)),
        song_popularity=float(raw.get("song_popularity", default.song_popularity)),
    )


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
    gmail_raw = raw.get("gmail", {}) or {}
    movie_raw = raw.get("movie_recommender", {}) or {}
    weights_raw = movie_raw.get("weights", {}) or {}
    spotify_raw = raw.get("spotify", {}) or {}
    music_raw = raw.get("music_recommender", {}) or {}
    mweights_raw = music_raw.get("weights", {}) or {}
    mzones_raw = music_raw.get("zones", {}) or {}

    api_key = os.environ.get("TMDB_API_KEY") or str(tmdb_raw.get("api_key", "") or "")
    omdb_api_key = os.environ.get("OMDB_API_KEY") or str(omdb_raw.get("api_key", "") or "")
    spotify_client_id = os.environ.get("SPOTIFY_CLIENT_ID") or str(spotify_raw.get("client_id", "") or "")
    spotify_client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET") or str(
        spotify_raw.get("client_secret", "") or ""
    )

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
        gmail=GmailConfig(
            credentials_path=(
                os.environ.get("GMAIL_CREDENTIALS_PATH")
                or str(gmail_raw.get("credentials_path", "") or "")
            ).strip(),
            max_emails=int(gmail_raw.get("max_emails", 50)),
            token_path=str(gmail_raw.get("token_path", "") or "").strip(),
        ),
        spotify=SpotifyConfig(
            client_id=spotify_client_id.strip(),
            client_secret=spotify_client_secret.strip(),
        ),
        music_recommender=MusicRecommenderConfig(
            weights=MusicRecommenderWeights(
                song_genre=float(mweights_raw.get("song_genre", 0.30)),
                song_audio_features=float(mweights_raw.get("song_audio_features", 0.25)),
                song_artist_affinity=float(mweights_raw.get("song_artist_affinity", 0.20)),
                song_year=float(mweights_raw.get("song_year", 0.15)),
                song_popularity=float(mweights_raw.get("song_popularity", 0.10)),
                artist_genre=float(mweights_raw.get("artist_genre", 0.40)),
                artist_related_artists=float(mweights_raw.get("artist_related_artists", 0.25)),
                artist_popularity=float(mweights_raw.get("artist_popularity", 0.20)),
                artist_era=float(mweights_raw.get("artist_era", 0.15)),
            ),
            zones=MusicZoneConfig(
                safe=_load_zone_weights(mzones_raw.get("safe", {}), MusicZoneWeights(
                    song_genre=0.20, song_audio_features=0.25, song_artist_affinity=0.35,
                    song_year=0.10, song_popularity=0.10,
                )),
                stretch=_load_zone_weights(mzones_raw.get("stretch", {}), MusicZoneWeights(
                    song_genre=0.45, song_audio_features=0.30, song_artist_affinity=0.00,
                    song_year=0.10, song_popularity=0.15,
                )),
                wild_card=_load_zone_weights(mzones_raw.get("wild_card", {}), MusicZoneWeights(
                    song_genre=0.20, song_audio_features=0.25, song_artist_affinity=0.00,
                    song_year=0.05, song_popularity=-0.15,
                )),
            ),
        ),
    )
