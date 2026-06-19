from __future__ import annotations

from agent_hub.agents.gmail_assistant.gmail import RawEmail
from agent_hub.agents.gmail_assistant.llm import EmailResult
from agent_hub.agents.gmail_assistant.logic import (
    InboxSummary,
    clear_inbox_snapshot,
    load_inbox_snapshot,
    save_inbox_snapshot,
)
from agent_hub.core.config import HubConfig


def _sample_result(msg_id: str = "abc") -> EmailResult:
    email = RawEmail(
        msg_id=msg_id,
        thread_id="t1",
        subject="Hello",
        sender="test@example.com",
        date="today",
        snippet="snippet",
        body="body",
    )
    return EmailResult(
        msg_id=msg_id,
        subject="Hello",
        sender="test@example.com",
        date="today",
        summary="Summary text",
        importance=8,
        category="Work",
        should_delete=False,
        delete_reason="",
        raw=email,
    )


def test_inbox_snapshot_roundtrip(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    result = _sample_result()
    summary = InboxSummary(
        results=[result],
        by_category={"Work": [result], "Finance": []},
        suggested_deletes=[],
        priority=[result],
        cached_count=1,
        analyzed_count=0,
    )
    save_inbox_snapshot(summary, config)
    loaded = load_inbox_snapshot(config)
    assert loaded is not None
    assert len(loaded.results) == 1
    assert loaded.results[0].category == "Work"
    assert loaded.by_category["Work"][0].msg_id == "abc"
    clear_inbox_snapshot(config)
    assert load_inbox_snapshot(config) is None
