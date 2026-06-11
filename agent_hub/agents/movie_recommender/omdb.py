from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from agent_hub.core.config import HubConfig, load_config

OMDB_BASE_URL = "http://www.omdbapi.com/"


@dataclass
class OmdbDetails:
    rotten_tomatoes_score: str | None = None
    metacritic_score: str | None = None
    imdb_rating: str | None = None


def _api_key(config: HubConfig | None = None) -> str | None:
    config = config or load_config()
    key = os.environ.get("OMDB_API_KEY") or config.omdb.api_key.strip()
    return key or None


def omdb_configured(config: HubConfig | None = None) -> bool:
    return _api_key(config) is not None


def parse_percent_score(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", value)
    if match:
        return float(match.group(1))
    return None


def parse_imdb_rating(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", value)
    if match:
        return float(match.group(1)) * 10.0
    return None


def parse_metacritic_score(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+)", value)
    if match:
        return float(match.group(1))
    return None


def fetch_omdb_details(imdb_id: str | None, config: HubConfig | None = None) -> OmdbDetails | None:
    if not imdb_id:
        return None
    api_key = _api_key(config)
    if not api_key:
        return None

    query = urllib.parse.urlencode({"i": imdb_id, "apikey": api_key})
    url = f"{OMDB_BASE_URL}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None

    if payload.get("Response") != "True":
        return None

    details = OmdbDetails(imdb_rating=payload.get("imdbRating"))
    for rating in payload.get("Ratings", []):
        source = rating.get("Source")
        value = rating.get("Value")
        if source == "Rotten Tomatoes" and value:
            details.rotten_tomatoes_score = str(value)
        elif source == "Metacritic" and value:
            details.metacritic_score = str(value)
    return details


def fetch_rotten_tomatoes_score(imdb_id: str | None, config: HubConfig | None = None) -> str | None:
    details = fetch_omdb_details(imdb_id, config=config)
    return details.rotten_tomatoes_score if details else None
