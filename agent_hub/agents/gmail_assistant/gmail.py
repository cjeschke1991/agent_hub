from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Any

from agent_hub.core.config import HubConfig
from agent_hub.core.parallel import map_parallel

_FETCH_WORKERS = 8
_METADATA_HEADERS = ["From", "Subject", "Date"]


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


def fetch_emails(
    service,
    max_results: int = 50,
    label: str = "INBOX",
    *,
    config: HubConfig | None = None,
) -> list[RawEmail]:
    """Fetch up to *max_results* emails from *label*.

    When *config* is provided, reuses locally cached messages for emails that
    already have cached analysis, avoiding full Gmail downloads on refresh.
    """
    result = (
        service.users()
        .messages()
        .list(userId="me", labelIds=[label], maxResults=max_results)
        .execute()
    )
    message_ids = [stub["id"] for stub in result.get("messages", []) if stub.get("id")]
    if not message_ids:
        return []

    if config is None:
        return _fetch_full_messages(service, message_ids)

    from agent_hub.agents.gmail_assistant.analysis_cache import load_cached_analysis
    from agent_hub.agents.gmail_assistant.message_cache import (
        load_cached_message,
        save_cached_message,
    )

    cfg = config
    cached_emails: dict[str, RawEmail] = {}
    to_fetch_meta: list[str] = []
    to_fetch_full: list[str] = []

    for msg_id in message_ids:
        if load_cached_analysis(msg_id, cfg) and (email := load_cached_message(msg_id, cfg)):
            cached_emails[msg_id] = email
        elif load_cached_analysis(msg_id, cfg):
            to_fetch_meta.append(msg_id)
        else:
            to_fetch_full.append(msg_id)

    meta_by_id = _fetch_messages_by_id(service, to_fetch_meta, _fetch_metadata_message)
    full_by_id = _fetch_messages_by_id(service, to_fetch_full, _fetch_full_message)

    for email in (*meta_by_id.values(), *full_by_id.values()):
        save_cached_message(email, cfg)

    emails: list[RawEmail] = []
    for msg_id in message_ids:
        if msg_id in cached_emails:
            emails.append(cached_emails[msg_id])
        elif msg_id in meta_by_id:
            emails.append(meta_by_id[msg_id])
        elif msg_id in full_by_id:
            emails.append(full_by_id[msg_id])
    return emails


def _fetch_full_messages(service, message_ids: list[str]) -> list[RawEmail]:
    by_id = _fetch_messages_by_id(service, message_ids, _fetch_full_message)
    return [by_id[msg_id] for msg_id in message_ids if msg_id in by_id]


def _fetch_messages_by_id(
    service,
    message_ids: list[str],
    fetch_fn,
) -> dict[str, RawEmail]:
    if not message_ids:
        return {}

    def _fetch_one(msg_id: str) -> RawEmail | None:
        return fetch_fn(service, msg_id)

    fetched = map_parallel(message_ids, _fetch_one, max_workers=_FETCH_WORKERS)
    return {
        message_ids[idx]: email
        for idx, email in enumerate(fetched)
        if email is not None
    }


def _fetch_full_message(service, msg_id: str) -> RawEmail | None:
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )
    return _parse_message(msg)


def _fetch_metadata_message(service, msg_id: str) -> RawEmail | None:
    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=msg_id,
            format="metadata",
            metadataHeaders=_METADATA_HEADERS,
        )
        .execute()
    )
    return _parse_message(msg)


def trash_email(service, msg_id: str) -> None:
    """Move an email to Trash."""
    service.users().messages().trash(userId="me", id=msg_id).execute()


def send_email(service, *, to: str, subject: str, body: str) -> dict[str, Any]:
    """Send a plain-text email from the authenticated Gmail account."""
    from email.mime.text import MIMEText

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()


def mark_read(service, msg_id: str) -> None:
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


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
