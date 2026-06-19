"""High-level orchestration for the Gmail Assistant."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_hub.agents.gmail_assistant.analysis_cache import (
    load_cached_analysis,
    result_from_cache,
    save_cached_analysis,
)
from agent_hub.agents.gmail_assistant.auth import (
    calendar_scope_granted,
    get_calendar_service,
    get_gmail_service,
)
from agent_hub.agents.gmail_assistant.calendar import (
    calendar_emails_from_events,
    fetch_upcoming_events,
    format_calendar_context,
)
from agent_hub.agents.gmail_assistant.gmail import RawEmail, fetch_emails, send_email, trash_email
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
    cached_count: int = 0
    analyzed_count: int = 0


def _split_cached_emails(
    emails: list[RawEmail],
    config: HubConfig,
) -> tuple[list[EmailResult], list[RawEmail]]:
    cached_results: list[EmailResult] = []
    to_analyze: list[RawEmail] = []
    for email in emails:
        entry = load_cached_analysis(email.msg_id, config)
        if entry:
            cached_results.append(result_from_cache(entry, email))
        else:
            to_analyze.append(email)
    return cached_results, to_analyze


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
    cached_results, to_analyze = _split_cached_emails(raw_emails, cfg)

    newly_analyzed = analyze_emails_batch(to_analyze, pref_context, prefs=prefs)
    for result in newly_analyzed:
        if not result.summary.startswith("[Analysis failed:"):
            save_cached_analysis(result, cfg)

    analyzed_by_id = {r.msg_id: r for r in cached_results + newly_analyzed}
    analyzed = [analyzed_by_id[email.msg_id] for email in raw_emails if email.msg_id in analyzed_by_id]

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
        cached_count=len(cached_results),
        analyzed_count=len(newly_analyzed),
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


def send_morning_email(config: HubConfig | None = None, *, to: str | None = None) -> str:
    """Send the configured daily morning email. Returns the Gmail message id."""
    cfg = config or load_config()
    morning = cfg.gmail.morning_email
    recipient = (to or morning.to).strip()
    if not recipient:
        raise ValueError("Morning email recipient is not configured.")
    service = get_gmail_service(cfg)
    sent = send_email(
        service,
        to=recipient,
        subject=morning.subject.strip(),
        body=morning.body,
    )
    return str(sent.get("id", ""))
