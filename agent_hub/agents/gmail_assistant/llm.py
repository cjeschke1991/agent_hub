from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from agent_hub.agents.gmail_assistant.gmail import RawEmail
from agent_hub.agents.gmail_assistant.prefs import (
    GmailPrefs,
    get_sender_reputation,
    is_vip_sender,
)
from agent_hub.core.parallel import map_parallel

_LLM_WORKERS = 5

CATEGORIES = [
    "Finance",
    "Work",
    "Shopping",
    "Social",
    "News & Newsletters",
    "Travel",
    "Health",
    "Other",
]

_SYSTEM_PROMPT = """\
You are an intelligent email assistant. Analyze the email carefully and return JSON with:
- "summary": 1-3 sentences covering key points and any action needed.
- "requires_action": true if the user must reply, pay, sign, or do something; false otherwise.
- "deadline": ISO date or human-readable deadline if mentioned, else empty string.
- "importance": integer 0-10 (10 = extremely urgent/important, 0 = spam/irrelevant).
- "urgency_reason": short phrase explaining the importance score.
- "category": one of """ + json.dumps(CATEGORIES) + """.
- "should_delete": true only for clear junk (spam, promos, automated notifications with no value).
- "delete_confidence": float 0.0-1.0 — how confident you are deletion is safe.
- "delete_reason": short phrase if should_delete is true, else empty string.

Be conservative: when unsure about deletion, set should_delete=false and delete_confidence below 0.5.
VIP senders and protected senders must never be marked for deletion.

Reply with valid JSON only. No markdown fences, no extra text.
"""


@dataclass
class EmailResult:
    msg_id: str
    subject: str
    sender: str
    date: str
    summary: str
    importance: int
    category: str
    should_delete: bool
    delete_reason: str
    raw: RawEmail = field(repr=False)
    urgency_reason: str = ""
    delete_confidence: float = 0.0
    requires_action: bool = False
    deadline: str = ""


def analyze_email(
    email: RawEmail,
    pref_context: str = "",
    *,
    prefs: GmailPrefs | None = None,
    score_context: str = "",
) -> EmailResult:
    user_content = _build_user_prompt(email, pref_context, prefs=prefs, score_context=score_context)
    response_text = _call_llm(user_content)
    data = _parse_json(response_text)
    return EmailResult(
        msg_id=email.msg_id,
        subject=email.subject,
        sender=email.sender,
        date=email.date,
        summary=data.get("summary", ""),
        importance=int(data.get("importance", 5)),
        category=data.get("category", "Other"),
        should_delete=bool(data.get("should_delete", False)),
        delete_reason=str(data.get("delete_reason", "")),
        urgency_reason=str(data.get("urgency_reason", "")),
        delete_confidence=float(data.get("delete_confidence", 0.0)),
        requires_action=bool(data.get("requires_action", False)),
        deadline=str(data.get("deadline", "")),
        raw=email,
    )


def analyze_emails_batch(
    emails: list[RawEmail],
    pref_context: str = "",
    *,
    prefs: GmailPrefs | None = None,
    score_context_fn: "Callable[[RawEmail], str] | None" = None,
) -> list[EmailResult]:
    if not emails:
        return []

    def _analyze_one(email: RawEmail) -> EmailResult:
        sc = score_context_fn(email) if score_context_fn else ""
        try:
            return analyze_email(email, pref_context, prefs=prefs, score_context=sc)
        except Exception as exc:
            return EmailResult(
                msg_id=email.msg_id,
                subject=email.subject,
                sender=email.sender,
                date=email.date,
                summary=f"[Analysis failed: {exc}]",
                importance=5,
                category="Other",
                should_delete=False,
                delete_reason="",
                raw=email,
                urgency_reason="analysis failed",
                delete_confidence=0.0,
                requires_action=False,
                deadline="",
            )

    analyzed = map_parallel(emails, _analyze_one, max_workers=_LLM_WORKERS)
    return [result for result in analyzed if result is not None]


def _build_user_prompt(
    email: RawEmail,
    pref_context: str,
    *,
    prefs: GmailPrefs | None = None,
    score_context: str = "",
) -> str:
    parts: list[str] = []
    if pref_context:
        parts.append(f"Shared context:\n{pref_context}\n")

    if prefs:
        rep = get_sender_reputation(email.sender, prefs)
        if rep.keep or rep.delete:
            parts.append(
                f"Sender history: kept {rep.keep}×, deleted {rep.delete}× by user."
            )
        if is_vip_sender(email.sender, prefs):
            parts.append("This sender is VIP — treat as high importance, never delete.")

    if score_context:
        parts.append(score_context)

    parts.extend(
        [
            f"Subject: {email.subject}",
            f"From: {email.sender}",
            f"Date: {email.date}",
            "",
            email.body or email.snippet or "(empty)",
        ]
    )
    return "\n".join(parts)


def _call_llm(user_content: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to your .env file to use the Gmail Assistant."
        )
    from openai import OpenAI  # type: ignore[import]

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
