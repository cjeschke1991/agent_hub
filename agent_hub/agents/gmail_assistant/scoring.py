"""Safety gates and importance adjustments for email recommendations."""
from __future__ import annotations

from dataclasses import replace

from agent_hub.agents.gmail_assistant.llm import EmailResult
from agent_hub.agents.gmail_assistant.prefs import (
    GmailPrefs,
    extract_sender_email,
    is_protected_sender,
    is_vip_sender,
    sender_matches_list,
)

DELETE_CONFIDENCE_THRESHOLD = 0.85
MAX_IMPORTANCE_FOR_DELETE = 3
VIP_BOOST = 2
KEYWORD_BOOST = 1
REPUTATION_KEEP_BOOST = 1


def apply_safety_gates(
    result: EmailResult,
    prefs: GmailPrefs,
) -> EmailResult:
    """Adjust importance and suppress unsafe delete suggestions."""
    importance = result.importance
    urgency_bits: list[str] = []

    if is_vip_sender(result.sender, prefs):
        importance += VIP_BOOST
        urgency_bits.append("VIP sender")

    rep = prefs.sender_reputation.get(extract_sender_email(result.sender))
    if rep and rep.keep >= 2:
        importance += REPUTATION_KEEP_BOOST
        urgency_bits.append(f"kept {rep.keep}× before")

    combined_text = f"{result.subject} {result.summary} {result.raw.body}".lower()
    for keyword in prefs.boost_keywords:
        if keyword.lower() in combined_text:
            importance += KEYWORD_BOOST
            urgency_bits.append(f"keyword: {keyword}")
            break

    if result.deadline:
        urgency_bits.append(f"deadline: {result.deadline}")

    importance = max(0, min(10, importance))

    should_delete = result.should_delete
    delete_reason = result.delete_reason

    if should_delete:
        if is_protected_sender(result.sender, prefs):
            should_delete = False
            delete_reason = ""
        elif importance > MAX_IMPORTANCE_FOR_DELETE:
            should_delete = False
            delete_reason = ""
        elif result.delete_confidence < DELETE_CONFIDENCE_THRESHOLD:
            should_delete = False
            delete_reason = ""
        elif sender_matches_list(result.sender, prefs.vip_senders):
            should_delete = False
            delete_reason = ""

    urgency_reason = result.urgency_reason
    if urgency_bits:
        extra = "; ".join(urgency_bits)
        urgency_reason = f"{urgency_reason}; {extra}" if urgency_reason else extra

    return replace(
        result,
        importance=importance,
        should_delete=should_delete,
        delete_reason=delete_reason,
        urgency_reason=urgency_reason,
    )
