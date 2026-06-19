from __future__ import annotations

import base64
import email as email_lib
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawEmail:
    msg_id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    snippet: str
    body: str
    labels: list[str] = field(default_factory=list)
    is_read: bool = True


def fetch_emails(service, max_results: int = 50, label: str = "INBOX") -> list[RawEmail]:
    """Fetch up to *max_results* emails from *label*."""
    result = (
        service.users()
        .messages()
        .list(userId="me", labelIds=[label], maxResults=max_results)
        .execute()
    )
    messages = result.get("messages", [])
    emails: list[RawEmail] = []
    for msg_stub in messages:
        msg_id = msg_stub["id"]
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )
        emails.append(_parse_message(msg))
    return emails


def trash_email(service, msg_id: str) -> None:
    """Move an email to Trash."""
    service.users().messages().trash(userId="me", id=msg_id).execute()


def mark_read(service, msg_id: str) -> None:
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _header(headers: list[dict[str, str]], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_body(data: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(data + "==")
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_text(payload: dict[str, Any]) -> str:
    mime = payload.get("mimeType", "")
    parts = payload.get("parts", [])

    if mime == "text/plain":
        body_data = payload.get("body", {}).get("data", "")
        return _decode_body(body_data)

    if mime == "text/html" and not parts:
        body_data = payload.get("body", {}).get("data", "")
        html = _decode_body(body_data)
        return re.sub(r"<[^>]+>", " ", html)

    text = ""
    for part in parts:
        candidate = _extract_text(part)
        if candidate.strip():
            text = candidate
            if part.get("mimeType") == "text/plain":
                break
    return text


def _parse_message(msg: dict[str, Any]) -> RawEmail:
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    labels = msg.get("labelIds", [])

    body = _extract_text(payload).strip()
    # Truncate very long bodies to avoid blowing LLM context windows
    if len(body) > 4000:
        body = body[:4000] + "\n[… truncated …]"

    return RawEmail(
        msg_id=msg["id"],
        thread_id=msg.get("threadId", ""),
        subject=_header(headers, "subject") or "(no subject)",
        sender=_header(headers, "from"),
        date=_header(headers, "date"),
        snippet=msg.get("snippet", ""),
        body=body,
        labels=labels,
        is_read="UNREAD" not in labels,
    )
