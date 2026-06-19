"""High-level orchestration for the Gmail Assistant."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_hub.agents.gmail_assistant.analysis_cache import (
    load_all_cached_results,
    load_cached_analysis,
    result_from_cache,
    save_cached_analysis,
)
from agent_hub.agents.gmail_assistant.message_cache import save_cached_message
from agent_hub.agents.gmail_assistant.auth import get_gmail_service
from agent_hub.agents.gmail_assistant.gmail import RawEmail, fetch_emails, send_email, trash_email
from agent_hub.agents.gmail_assistant.llm import CATEGORIES, EmailResult, analyze_emails_batch
from agent_hub.agents.gmail_assistant.prefs import (
    load_prefs,
    prefs_to_context,
    record_delete,
    record_keep,
)
from agent_hub.agents.gmail_assistant.user_scores import sender_score_context
from agent_hub.agents.gmail_assistant.scoring import apply_safety_gates
from agent_hub.core.api_cache import cache_get_pickle, cache_set_pickle
from agent_hub.core.config import HubConfig, load_config

PRIORITY_TOP_N = 5
_SNAPSHOT_NAMESPACE = "gmail_inbox"
_SNAPSHOT_KEY = "last_summary"


@dataclass
class InboxSummary:
    results: list[EmailResult] = field(default_factory=list)
    by_category: dict[str, list[EmailResult]] = field(default_factory=dict)
    suggested_deletes: list[EmailResult] = field(default_factory=list)
    priority: list[EmailResult] = field(default_factory=list)
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
            # Build result, merging live email headers into any old cache entries
            # that were saved before header fields were stored in the JSON.
            merged = {**entry, "msg_id": email.msg_id, "subject": email.subject,
                      "sender": email.sender, "date": email.date, "snippet": email.snippet}
            result = result_from_cache(merged)
            if result is not None:
                # Persist header fields so future disk-only loads skip Gmail entirely.
                if not entry.get("subject"):
                    save_cached_analysis(result, config)
                cached_results.append(result)
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
    pref_context = prefs_to_context(prefs)

    raw_emails = fetch_emails(service, max_results=cfg.gmail.max_emails, label=label, config=cfg)
    cached_results, to_analyze = _split_cached_emails(raw_emails, cfg)

    newly_analyzed = analyze_emails_batch(
        to_analyze,
        pref_context,
        prefs=prefs,
        score_context_fn=lambda email: sender_score_context(email.sender, cfg),
    )
    for result in newly_analyzed:
        if not result.summary.startswith("[Analysis failed:"):
            save_cached_analysis(result, cfg)
            save_cached_message(result.raw, cfg)

    for result in cached_results:
        save_cached_message(result.raw, cfg)

    analyzed_by_id = {r.msg_id: r for r in cached_results + newly_analyzed}
    analyzed = [analyzed_by_id[email.msg_id] for email in raw_emails if email.msg_id in analyzed_by_id]

    results = [apply_safety_gates(r, prefs) for r in analyzed]

    by_category: dict[str, list[EmailResult]] = {cat: [] for cat in CATEGORIES}
    suggested_deletes: list[EmailResult] = []

    for r in results:
        cat = r.category if r.category in by_category else "Other"
        by_category[cat].append(r)
        if r.should_delete:
            suggested_deletes.append(r)

    results_sorted = sorted(results, key=lambda x: x.importance, reverse=True)
    priority = results_sorted[:PRIORITY_TOP_N]

    summary = InboxSummary(
        results=results_sorted,
        by_category=by_category,
        suggested_deletes=suggested_deletes,
        priority=priority,
        cached_count=len(cached_results),
        analyzed_count=len(newly_analyzed),
    )
    save_inbox_snapshot(summary, cfg)
    return summary


def rebuild_inbox_from_cache(config: HubConfig | None = None) -> InboxSummary | None:
    """Build an InboxSummary entirely from disk — no Gmail or AI calls.

    Returns None if the cache is empty.  Results may be slightly stale (emails
    that have been deleted or moved since the last fetch will still appear) but
    they load instantly and give the user something to read immediately.
    """
    cfg = config or load_config()
    raw_results = load_all_cached_results(cfg)
    if not raw_results:
        return None

    # Deduplicate by msg_id (last-write wins from the cache directory scan).
    seen: dict[str, EmailResult] = {}
    for r in raw_results:
        seen[r.msg_id] = r
    raw_results = list(seen.values())

    prefs = load_prefs(cfg)
    results = [apply_safety_gates(r, prefs) for r in raw_results]
    results_sorted = sorted(results, key=lambda x: x.importance, reverse=True)

    by_category: dict[str, list[EmailResult]] = {cat: [] for cat in CATEGORIES}
    suggested_deletes: list[EmailResult] = []
    for r in results_sorted:
        cat = r.category if r.category in by_category else "Other"
        by_category[cat].append(r)
        if r.should_delete:
            suggested_deletes.append(r)

    priority = results_sorted[:PRIORITY_TOP_N]

    summary = InboxSummary(
        results=results_sorted,
        by_category=by_category,
        suggested_deletes=suggested_deletes,
        priority=priority,
        cached_count=len(results_sorted),
        analyzed_count=0,
    )
    save_inbox_snapshot(summary, cfg)
    return summary


def save_inbox_snapshot(summary: InboxSummary, config: HubConfig | None = None) -> None:
    """Persist the last inbox view so Categories/Inbox tabs work after refresh."""
    cfg = config or load_config()
    cache_set_pickle(cfg.data_dir, _SNAPSHOT_NAMESPACE, _SNAPSHOT_KEY, summary)


def load_inbox_snapshot(config: HubConfig | None = None) -> InboxSummary | None:
    cfg = config or load_config()
    snapshot = cache_get_pickle(cfg.data_dir, _SNAPSHOT_NAMESPACE, _SNAPSHOT_KEY)
    return snapshot if isinstance(snapshot, InboxSummary) else None


def clear_inbox_snapshot(config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    path = cfg.data_dir / "cache" / _SNAPSHOT_NAMESPACE / f"{_SNAPSHOT_KEY}.pkl"
    if path.exists():
        path.unlink()


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
