from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent_hub.agents.gmail_assistant.gmail import RawEmail
from agent_hub.agents.gmail_assistant.llm import (
    EmailResult,
    _parse_json,
    analyze_email,
)


def _make_email(**kwargs) -> RawEmail:
    defaults = dict(
        msg_id="abc123",
        thread_id="thread1",
        subject="Test subject",
        sender="test@example.com",
        date="Thu, 18 Jun 2026 10:00:00 -0500",
        snippet="Short snippet",
        body="Hello, this is a test email body.",
        labels=[],
        is_read=True,
    )
    defaults.update(kwargs)
    return RawEmail(**defaults)


def test_parse_json_returns_dict():
    raw = '{"summary": "Hello", "importance": 7, "category": "Work", "should_delete": false, "delete_reason": ""}'
    result = _parse_json(raw)
    assert result["importance"] == 7
    assert result["category"] == "Work"


def test_parse_json_strips_markdown_fences():
    raw = '```json\n{"summary": "Hi"}\n```'
    result = _parse_json(raw)
    assert result["summary"] == "Hi"


def test_parse_json_returns_empty_on_invalid():
    assert _parse_json("not json at all") == {}


def test_analyze_email_calls_llm(monkeypatch):
    llm_response = json.dumps(
        {
            "summary": "A test email.",
            "importance": 8,
            "category": "Work",
            "should_delete": False,
            "delete_reason": "",
        }
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        "agent_hub.agents.gmail_assistant.llm._call_llm",
        lambda user_content: llm_response,
    )

    email = _make_email()
    result = analyze_email(email)

    assert isinstance(result, EmailResult)
    assert result.importance == 8
    assert result.category == "Work"
    assert result.summary == "A test email."
    assert result.should_delete is False


def test_analyze_email_no_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    email = _make_email()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        analyze_email(email)
