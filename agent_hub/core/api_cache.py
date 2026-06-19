from __future__ import annotations

import hashlib
import json
import pickle
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _cache_file(data_dir: Path, namespace: str, key: str, *, ext: str) -> Path:
    path = Path(data_dir) / "cache" / namespace / f"{key}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def cache_get_json(
    data_dir: Path,
    namespace: str,
    key: str,
    *,
    ttl_seconds: int | None = None,
) -> Any | None:
    path = _cache_file(data_dir, namespace, key, ext="json")
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if ttl_seconds is not None:
            age = time.time() - float(payload.get("_cached_at", 0))
            if age > ttl_seconds:
                return None
        return payload.get("value")
    except Exception:
        return None


def cache_set_json(data_dir: Path, namespace: str, key: str, value: Any) -> None:
    path = _cache_file(data_dir, namespace, key, ext="json")
    path.write_text(
        json.dumps({"_cached_at": time.time(), "value": value}, indent=2),
        encoding="utf-8",
    )


def cache_get_pickle(
    data_dir: Path,
    namespace: str,
    key: str,
    *,
    ttl_seconds: int | None = None,
) -> Any | None:
    path = _cache_file(data_dir, namespace, key, ext="pkl")
    if not path.exists():
        return None
    try:
        if ttl_seconds is not None:
            age = time.time() - path.stat().st_mtime
            if age > ttl_seconds:
                return None
        with path.open("rb") as handle:
            return pickle.load(handle)
    except Exception:
        return None


def cache_set_pickle(data_dir: Path, namespace: str, key: str, value: Any) -> None:
    path = _cache_file(data_dir, namespace, key, ext="pkl")
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def cache_clear_namespace(data_dir: Path, namespace: str) -> int:
    """Delete all cached entries in *namespace*. Returns files removed."""
    directory = Path(data_dir) / "cache" / namespace
    if not directory.exists():
        return 0
    removed = 0
    for path in directory.iterdir():
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def cache_count_namespace(data_dir: Path, namespace: str) -> int:
    directory = Path(data_dir) / "cache" / namespace
    if not directory.exists():
        return 0
    return sum(1 for path in directory.iterdir() if path.is_file())
