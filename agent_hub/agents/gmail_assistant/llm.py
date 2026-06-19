from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from agent_hub.agents.gmail_assistant.gmail import RawEmail

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
You are an intelligent email assistant. Given an email, return a JSON object with:
- "summary": a 1-3 sentence plain-English summary of the key points.
- "importance": an integer 0-10 (10 = extremely urgent/important, 0 = spam/irrelevant).
- "category": one of """ + json.dumps(CATEGORIES) + """.
- "should_delete": true if this email is clearly safe to delete (spam, promotions, automated notifications), false otherwise.
- "delete_reason": a short phrase explaining why it should be deleted (empty string if should_delete is false).

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


def analyze_email(email: RawEmail, pref_context: str = "") -> EmailResult:
    """Call the LLM to analyze a single email and return a structured result."""
    user_content = _build_user_prompt(email, pref_context)
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
        raw=email,
    )


def analyze_emails_batch(
    emails: list[RawEmail], pref_context: str = ""
) -> list[EmailResult]:
    results: list[EmailResult] = []
    for email in emails:
        try:
            results.append(analyze_email(email, pref_context))
        except Exception as exc:
            results.append(
                EmailResult(
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
                )
            )
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_user_prompt(email: RawEmail, pref_context: str) -> str:
    parts = [
        f"Subject: {email.subject}",
        f"From: {email.sender}",
        f"Date: {email.date}",
        "",
        email.body or email.snippet or "(empty)",
    ]
    if pref_context:
        parts = [f"User preferences:\n{pref_context}\n"] + parts
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
        max_tokens=400,
    )
    return response.choices[0].message.content or ""


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip optional markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
