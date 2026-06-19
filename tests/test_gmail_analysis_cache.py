from __future__ import annotations

from agent_hub.agents.gmail_assistant.analysis_cache import (
    load_cached_analysis,
    result_from_cache,
    save_cached_analysis,
)
from agent_hub.agents.gmail_assistant.gmail import RawEmail
from agent_hub.agents.gmail_assistant.llm import EmailResult
from agent_hub.core.config import HubConfig


def test_analysis_cache_roundtrip(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    email = RawEmail(
        msg_id="abc",
        thread_id="t1",
        subject="Hello",
        sender="test@example.com",
        date="today",
        snippet="snippet",
        body="body",
    )
    result = EmailResult(
        msg_id="abc",
        subject="Hello",
        sender="test@example.com",
        date="today",
        summary="Summary text",
        importance=8,
        category="Work",
        should_delete=False,
        delete_reason="",
        raw=email,
        urgency_reason="urgent",
        delete_confidence=0.1,
        requires_action=True,
        deadline="tomorrow",
    )
    save_cached_analysis(result, config)
    cached = load_cached_analysis("abc", config)
    assert cached is not None
    rebuilt = result_from_cache(cached, email)
    assert rebuilt.summary == "Summary text"
    assert rebuilt.importance == 8
    assert rebuilt.requires_action is True
