from __future__ import annotations

import pytest

from agent_hub.agents.gmail_assistant.gmail import RawEmail
from agent_hub.agents.gmail_assistant.llm import EmailResult
from agent_hub.agents.gmail_assistant.prefs import GmailPrefs, SenderReputation
from agent_hub.agents.gmail_assistant.scoring import apply_safety_gates


def _email(**kwargs) -> EmailResult:
    defaults = dict(
        msg_id="1",
        subject="Hello",
        sender="Boss <boss@company.com>",
        date="today",
        summary="Please review",
        importance=5,
        category="Work",
        should_delete=False,
        delete_reason="",
        urgency_reason="",
        delete_confidence=0.0,
        requires_action=False,
        deadline="",
        raw=RawEmail(
            msg_id="1",
            thread_id="t1",
            subject="Hello",
            sender="boss@company.com",
            date="today",
            snippet="",
            body="Please review",
        ),
    )
    defaults.update(kwargs)
    return EmailResult(**defaults)


def test_vip_sender_never_gets_delete_suggestion():
    prefs = GmailPrefs(vip_senders=["boss@company.com"])
    result = _email(should_delete=True, delete_confidence=0.95, importance=5)
    gated = apply_safety_gates(result, prefs)
    assert gated.should_delete is False
    assert gated.importance >= 7


def test_protected_sender_blocks_delete():
    prefs = GmailPrefs(keep_senders=["boss@company.com"])
    result = _email(should_delete=True, delete_confidence=0.99, importance=1)
    gated = apply_safety_gates(result, prefs)
    assert gated.should_delete is False


def test_low_confidence_delete_suppressed():
    prefs = GmailPrefs()
    result = _email(should_delete=True, delete_confidence=0.5, importance=1)
    gated = apply_safety_gates(result, prefs)
    assert gated.should_delete is False


def test_high_importance_never_deleted():
    prefs = GmailPrefs()
    result = _email(should_delete=True, delete_confidence=0.99, importance=8)
    gated = apply_safety_gates(result, prefs)
    assert gated.should_delete is False


def test_keyword_boosts_importance():
    prefs = GmailPrefs(boost_keywords=["invoice"])
    result = _email(subject="Your invoice is ready", importance=4)
    gated = apply_safety_gates(result, prefs)
    assert gated.importance == 5


def test_reputation_keep_boosts_importance():
    prefs = GmailPrefs(
        sender_reputation={"boss@company.com": SenderReputation(keep=3, delete=0)}
    )
    result = _email(importance=4)
    gated = apply_safety_gates(result, prefs)
    assert gated.importance == 5


def test_safe_delete_passes_gates():
    prefs = GmailPrefs()
    result = _email(
        sender="promo@store.com",
        should_delete=True,
        delete_confidence=0.95,
        importance=2,
    )
    gated = apply_safety_gates(result, prefs)
    assert gated.should_delete is True
