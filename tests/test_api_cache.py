from __future__ import annotations

import time

import pytest

from agent_hub.core.api_cache import cache_get_json, cache_key, cache_set_json


def test_cache_key_is_stable():
    assert cache_key(1, ["a", "b"]) == cache_key(1, ["a", "b"])
    assert cache_key(1, ["b", "a"]) != cache_key(1, ["a", "b"])


def test_json_cache_roundtrip(tmp_path):
    cache_set_json(tmp_path, "test", "abc", {"hello": "world"})
    assert cache_get_json(tmp_path, "test", "abc") == {"hello": "world"}


def test_json_cache_expires(tmp_path):
    import json

    path = tmp_path / "cache" / "test" / "abc.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"_cached_at": time.time() - 7200, "value": {"hello": "world"}}),
        encoding="utf-8",
    )
    assert cache_get_json(tmp_path, "test", "abc", ttl_seconds=3600) is None
