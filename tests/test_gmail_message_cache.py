from __future__ import annotations

from unittest.mock import MagicMock, call

from agent_hub.agents.gmail_assistant.analysis_cache import save_cached_analysis
from agent_hub.agents.gmail_assistant.gmail import RawEmail, fetch_emails
from agent_hub.agents.gmail_assistant.llm import EmailResult
from agent_hub.agents.gmail_assistant.message_cache import (
    load_cached_message,
    save_cached_message,
)
from agent_hub.core.config import HubConfig


def _raw_email(msg_id: str = "abc") -> RawEmail:
    return RawEmail(
        msg_id=msg_id,
        thread_id="t1",
        subject="Hello",
        sender="test@example.com",
        date="today",
        snippet="snippet",
        body="body text",
    )


def _analysis_result(email: RawEmail) -> EmailResult:
    return EmailResult(
        msg_id=email.msg_id,
        subject=email.subject,
        sender=email.sender,
        date=email.date,
        summary="Summary text",
        importance=8,
        category="Work",
        should_delete=False,
        delete_reason="",
        raw=email,
    )


def test_message_cache_roundtrip(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    email = _raw_email()
    save_cached_message(email, config)
    loaded = load_cached_message("abc", config)
    assert loaded is not None
    assert loaded.subject == "Hello"
    assert loaded.body == "body text"


def test_fetch_emails_skips_gmail_download_when_fully_cached(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    email = _raw_email("msg1")
    save_cached_message(email, config)
    save_cached_analysis(_analysis_result(email), config)

    service = MagicMock()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg1"}]
    }
    get_mock = service.users.return_value.messages.return_value.get

    fetched = fetch_emails(service, config=config)

    assert len(fetched) == 1
    assert fetched[0].subject == "Hello"
    get_mock.assert_not_called()


def test_fetch_emails_uses_metadata_for_analysis_without_message_cache(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    email = _raw_email("msg2")
    save_cached_analysis(_analysis_result(email), config)

    service = MagicMock()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg2"}]
    }
    get_mock = service.users.return_value.messages.return_value.get
    get_mock.return_value.execute.return_value = {
        "id": "msg2",
        "threadId": "t2",
        "snippet": "snippet",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Hello"},
                {"name": "From", "value": "test@example.com"},
                {"name": "Date", "value": "today"},
            ]
        },
    }

    fetched = fetch_emails(service, config=config)

    assert len(fetched) == 1
    get_mock.assert_called_once_with(
        userId="me",
        id="msg2",
        format="metadata",
        metadataHeaders=["From", "Subject", "Date"],
    )
    assert load_cached_message("msg2", config) is not None
