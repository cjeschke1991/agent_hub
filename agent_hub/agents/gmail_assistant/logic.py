"""High-level orchestration for the Gmail Assistant."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_hub.agents.gmail_assistant.auth import calendar_scope_granted, get_calendar_service
from agent_hub.agents.gmail_assistant.calendar import (
    calendar_emails_from_events,
    fetch_upcoming_events,
    format_calendar_context,
)
from agent_hub.agents.gmail_assistant.gmail import fetch_emails, trash_email
from agent_hub.agents.gmail_assistant.llm import CATEGORIES, EmailResult, analyze_emails_batch
from agent_hub.agents.gmail_assistant.prefs import (
    load_prefs,
    prefs_to_context,
    record_delete,
    record_keep,
)
from agent_hub.agents.gmail_assistant.scoring import apply_safety_gates
from agent_hub.core.config import HubConfig, load_config

PRIORITY_TOP_N = 5


@dataclass
class InboxSummary:
    results: list[EmailResult] = field(default_factory=list)
    by_category: dict[str, list[EmailResult]] = field(default_factory=dict)
    suggested_deletes: list[EmailResult] = field(default_factory=list)
    priority: list[EmailResult] = field(default_factory=list)
    calendar_available: bool = True
    calendar_warning: str = ""


def load_and_analyze_inbox(
    service: Any,
    config: HubConfig | None = None,
    label: str = "INBOX",
) -> InboxSummary:
    cfg = config or load_config()
    prefs = load_prefs(cfg)

    calendar_context = ""
    calendar_emails: set[str] = set()
    calendar_available = True
    calendar_warning = ""

    if calendar_scope_granted(cfg):
        try:
            cal_service = get_calendar_service(cfg)
            events = fetch_upcoming_events(cal_service)
            calendar_context = format_calendar_context(events)
            calendar_emails = calendar_emails_from_events(events)
        except Exception as exc:
            calendar_available = False
            calendar_warning = f"Calendar unavailable: {exc}"
    else:
        calendar_available = False
        calendar_warning = (
            "Calendar access not granted. Sign out and sign in again to enable calendar-aware ranking."
        )

    pref_context = prefs_to_context(prefs, calendar_context=calendar_context)

    raw_emails = fetch_emails(service, max_results=cfg.gmail.max_emails, label=label)
    analyzed = analyze_emails_batch(raw_emails, pref_context, prefs=prefs)
    results = [
        apply_safety_gates(r, prefs, calendar_emails=calendar_emails) for r in analyzed
    ]

    by_category: dict[str, list[EmailResult]] = {cat: [] for cat in CATEGORIES}
    suggested_deletes: list[EmailResult] = []

    for r in results:
        cat = r.category if r.category in by_category else "Other"
        by_category[cat].append(r)
        if r.should_delete:
            suggested_deletes.append(r)

    results_sorted = sorted(results, key=lambda x: x.importance, reverse=True)
    priority = results_sorted[:PRIORITY_TOP_N]

    return InboxSummary(
        results=results_sorted,
        by_category=by_category,
        suggested_deletes=suggested_deletes,
        priority=priority,
        calendar_available=calendar_available,
        calendar_warning=calendar_warning,
    )


def delete_email_and_learn(
    service: Any,
    result: EmailResult,
    config: HubConfig | None = None,
) -> None:
    trash_email(service, result.msg_id)
    record_delete(result.sender, config=config)


def keep_email_and_learn(
    result: EmailResult,
    config: HubConfig | None = None,
) -> None:
    record_keep(result.sender, config=config)
