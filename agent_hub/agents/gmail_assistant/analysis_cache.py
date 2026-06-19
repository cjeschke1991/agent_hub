"""Disk cache for per-email LLM analysis (pre safety-gates)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_hub.agents.gmail_assistant.llm import EmailResult
from agent_hub.core.api_cache import (
    cache_clear_namespace,
    cache_count_namespace,
    cache_get_json,
    cache_set_json,
)
from agent_hub.core.config import HubConfig, load_config

_NAMESPACE = "gmail_analysis"

# AI-derived fields stored in the cache.
_AI_FIELDS = (
    "summary",
    "importance",
    "category",
    "should_delete",
    "delete_reason",
    "urgency_reason",
    "delete_confidence",
    "requires_action",
    "deadline",
)

# Email header fields also stored so we can rebuild without hitting Gmail.
_HEADER_FIELDS = ("subject", "sender", "date", "snippet")


def load_cached_analysis(msg_id: str, config: HubConfig | None = None) -> dict[str, Any] | None:
    cfg = config or load_config()
    return cache_get_json(cfg.data_dir, _NAMESPACE, msg_id)


def save_cached_analysis(result: EmailResult, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    payload: dict[str, Any] = {f: getattr(result, f) for f in _AI_FIELDS}
    # Also persist header fields so inbox can be rebuilt from disk alone.
    for f in _HEADER_FIELDS:
        payload[f] = getattr(result, f, "") or getattr(result.raw, f, "")
    payload["msg_id"] = result.msg_id
    cache_set_json(cfg.data_dir, _NAMESPACE, result.msg_id, payload)


def result_from_cache(entry: dict[str, Any]) -> EmailResult | None:
    """Rebuild an EmailResult purely from a cached analysis entry (no network needed)."""
    from agent_hub.agents.gmail_assistant.gmail import RawEmail

    msg_id = str(entry.get("msg_id", ""))
    if not msg_id:
        return None

    stub_email = RawEmail(
        msg_id=msg_id,
        thread_id="",
        subject=str(entry.get("subject", "")),
        sender=str(entry.get("sender", "")),
        date=str(entry.get("date", "")),
        snippet=str(entry.get("snippet", "")),
        body="",
    )
    return EmailResult(
        msg_id=msg_id,
        subject=stub_email.subject,
        sender=stub_email.sender,
        date=stub_email.date,
        summary=str(entry.get("summary", "")),
        importance=int(entry.get("importance", 5)),
        category=str(entry.get("category", "Other")),
        should_delete=bool(entry.get("should_delete", False)),
        delete_reason=str(entry.get("delete_reason", "")),
        raw=stub_email,
        urgency_reason=str(entry.get("urgency_reason", "")),
        delete_confidence=float(entry.get("delete_confidence", 0.0)),
        requires_action=bool(entry.get("requires_action", False)),
        deadline=str(entry.get("deadline", "")),
    )


def load_all_cached_results(config: HubConfig | None = None) -> list[EmailResult]:
    """Load every cached analysis from disk — no network call required."""
    cfg = config or load_config()
    directory = Path(cfg.data_dir) / "cache" / _NAMESPACE
    if not directory.exists():
        return []
    results: list[EmailResult] = []
    for path in directory.iterdir():
        if path.suffix != ".json":
            continue
        try:
            import json, time as _time
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry = payload.get("value") or payload  # handle wrapped or bare
            result = result_from_cache(entry)
            if result is not None:
                results.append(result)
        except Exception:
            continue
    return results


def analysis_cache_count(config: HubConfig | None = None) -> int:
    cfg = config or load_config()
    return cache_count_namespace(cfg.data_dir, _NAMESPACE)


def clear_analysis_cache(config: HubConfig | None = None) -> int:
    """Clear stored LLM analysis and cached message bodies. Returns analysis entries removed."""
    from agent_hub.agents.gmail_assistant.message_cache import clear_message_cache
    cfg = config or load_config()
    clear_message_cache(cfg)
    return cache_clear_namespace(cfg.data_dir, _NAMESPACE)
