"""High-level orchestration for the Gmail Assistant."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_hub.agents.gmail_assistant.gmail import RawEmail, fetch_emails, trash_email
from agent_hub.agents.gmail_assistant.llm import CATEGORIES, EmailResult, analyze_emails_batch
from agent_hub.agents.gmail_assistant.prefs import (
    GmailPrefs,
    load_prefs,
    prefs_to_context,
    record_delete,
    record_keep,
)
from agent_hub.core.config import HubConfig, load_config


@dataclass
class InboxSummary:
    results: list[EmailResult] = field(default_factory=list)
    by_category: dict[str, list[EmailResult]] = field(default_factory=dict)
    suggested_deletes: list[EmailResult] = field(default_factory=list)


def load_and_analyze_inbox(
    service: Any,
    config: HubConfig | None = None,
    label: str = "INBOX",
) -> InboxSummary:
    """Fetch emails and run LLM analysis on all of them."""
    cfg = config or load_config()
    prefs = load_prefs(cfg)
    pref_context = prefs_to_context(prefs)

    raw_emails: list[RawEmail] = fetch_emails(
        service, max_results=cfg.gmail.max_emails, label=label
    )
    results = analyze_emails_batch(raw_emails, pref_context=pref_context)

    by_category: dict[str, list[EmailResult]] = {cat: [] for cat in CATEGORIES}
    suggested_deletes: list[EmailResult] = []

    for r in results:
        cat = r.category if r.category in by_category else "Other"
        by_category[cat].append(r)
        if r.should_delete:
            suggested_deletes.append(r)

    results_sorted = sorted(results, key=lambda x: x.importance, reverse=True)

    return InboxSummary(
        results=results_sorted,
        by_category=by_category,
        suggested_deletes=suggested_deletes,
    )


def delete_email_and_learn(
    service: Any,
    result: EmailResult,
    config: HubConfig | None = None,
) -> None:
    """Trash an email and record the sender preference."""
    trash_email(service, result.msg_id)
    record_delete(result.sender, config=config)


def keep_email_and_learn(
    result: EmailResult,
    config: HubConfig | None = None,
) -> None:
    """Record that the sender of this email should NOT be auto-deleted."""
    record_keep(result.sender, config=config)
