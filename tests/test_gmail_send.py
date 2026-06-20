from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent_hub.agents.gmail_assistant.gmail import send_email
from agent_hub.agents.gmail_assistant.logic import send_morning_email
from agent_hub.core.config import GmailConfig, HubConfig, MorningEmailConfig


def test_send_email_builds_mime_and_calls_api():
    service = MagicMock()
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "msg123"
    }

    result = send_email(
        service,
        to="njeschke19@gmail.com",
        subject="Good morning!",
        body="Good morning to my AMAZING baby! :)",
    )

    assert result["id"] == "msg123"
    service.users.return_value.messages.return_value.send.assert_called_once()
    call_kwargs = service.users.return_value.messages.return_value.send.call_args.kwargs
    assert call_kwargs["userId"] == "me"
    assert "raw" in call_kwargs["body"]


def test_send_morning_email_allows_recipient_override(tmp_path):
    config = HubConfig(
        data_dir=tmp_path,
        gmail=GmailConfig(
            credentials_path=str(tmp_path / "creds.json"),
            morning_email=MorningEmailConfig(enabled=True, to="wife@example.com"),
        ),
    )
    (tmp_path / "creds.json").write_text("{}", encoding="utf-8")

    with patch("agent_hub.agents.gmail_assistant.logic.get_gmail_service") as get_service:
        service = MagicMock()
        get_service.return_value = service
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "abc"
        }
        message_id = send_morning_email(config, to="test@example.com")

    assert message_id == "abc"
    send_call = service.users.return_value.messages.return_value.send.call_args
    raw = send_call.kwargs["body"]["raw"]
    assert raw


def test_send_morning_email_raises_when_disabled(tmp_path):
    config = HubConfig(
        data_dir=tmp_path,
        gmail=GmailConfig(
            credentials_path=str(tmp_path / "creds.json"),
            morning_email=MorningEmailConfig(enabled=False, to="wife@example.com"),
        ),
    )
    try:
        send_morning_email(config)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "disabled" in str(exc).lower()
