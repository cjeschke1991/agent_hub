"""Disk cache for per-email LLM analysis (pre safety-gates)."""
from __future__ import annotations

from typing import Any

from agent_hub.agents.gmail_assistant.gmail import RawEmail
from agent_hub.agents.gmail_assistant.llm import EmailResult
from agent_hub.core.api_cache import cache_get_json, cache_set_json
from agent_hub.core.config import HubConfig, load_config

_NAMESPACE = "gmail_analysis"
_FIELDS = (
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


def load_cached_analysis(msg_id: str, config: HubConfig | None = None) -> dict[str, Any] | None:
    cfg = config or load_config()
    return cache_get_json(cfg.data_dir, _NAMESPACE, msg_id)


def save_cached_analysis(result: EmailResult, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    payload = {field: getattr(result, field) for field in _FIELDS}
    cache_set_json(cfg.data_dir, _NAMESPACE, result.msg_id, payload)


def result_from_cache(entry: dict[str, Any], email: RawEmail) -> EmailResult:
    return EmailResult(
        msg_id=email.msg_id,
        subject=email.subject,
        sender=email.sender,
        date=email.date,
        summary=str(entry.get("summary", "")),
        importance=int(entry.get("importance", 5)),
        category=str(entry.get("category", "Other")),
        should_delete=bool(entry.get("should_delete", False)),
        delete_reason=str(entry.get("delete_reason", "")),
        raw=email,
        urgency_reason=str(entry.get("urgency_reason", "")),
        delete_confidence=float(entry.get("delete_confidence", 0.0)),
        requires_action=bool(entry.get("requires_action", False)),
        deadline=str(entry.get("deadline", "")),
    )
