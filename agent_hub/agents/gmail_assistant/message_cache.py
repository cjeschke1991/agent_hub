"""Disk cache for fetched Gmail message metadata and bodies."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from agent_hub.agents.gmail_assistant.gmail import RawEmail
from agent_hub.core.api_cache import (
    cache_clear_namespace,
    cache_get_json,
    cache_set_json,
)
from agent_hub.core.config import HubConfig, load_config

_NAMESPACE = "gmail_messages"


def load_cached_message(msg_id: str, config: HubConfig | None = None) -> RawEmail | None:
    cfg = config or load_config()
    payload = cache_get_json(cfg.data_dir, _NAMESPACE, msg_id)
    if not payload:
        return None
    try:
        return RawEmail(
            msg_id=str(payload["msg_id"]),
            thread_id=str(payload.get("thread_id", "")),
            subject=str(payload.get("subject", "")),
            sender=str(payload.get("sender", "")),
            date=str(payload.get("date", "")),
            snippet=str(payload.get("snippet", "")),
            body=str(payload.get("body", "")),
            labels=list(payload.get("labels") or []),
            is_read=bool(payload.get("is_read", True)),
        )
    except (KeyError, TypeError):
        return None


def save_cached_message(email: RawEmail, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    cache_set_json(cfg.data_dir, _NAMESPACE, email.msg_id, asdict(email))


def clear_message_cache(config: HubConfig | None = None) -> int:
    cfg = config or load_config()
    return cache_clear_namespace(cfg.data_dir, _NAMESPACE)
