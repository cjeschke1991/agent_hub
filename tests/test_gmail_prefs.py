from __future__ import annotations

import pytest

from agent_hub.agents.gmail_assistant.prefs import (
    GmailPrefs,
    SenderReputation,
    extract_sender_email,
    is_protected_sender,
    is_vip_sender,
    load_prefs,
    prefs_to_context,
    record_delete,
    record_keep,
    record_low_value,
    record_vip,
    save_prefs,
)
from agent_hub.core.config import HubConfig


@pytest.fixture()
def prefs_config(tmp_path):
    return HubConfig(data_dir=tmp_path)


def test_load_prefs_returns_defaults_when_missing(prefs_config):
    prefs = load_prefs(prefs_config)
    assert prefs.delete_senders == []
    assert prefs.keep_senders == []
    assert prefs.vip_senders == []
    assert prefs.notes == ""


def test_save_and_load_roundtrip(prefs_config):
    prefs = GmailPrefs(
        delete_senders=["spam@example.com"],
        keep_senders=["boss@company.com"],
        vip_senders=["ceo@company.com"],
        delete_subjects=["unsubscribe"],
        boost_keywords=["invoice", "urgent"],
        sender_reputation={"spam@example.com": SenderReputation(keep=0, delete=3)},
        notes="Test note",
    )
    save_prefs(prefs, prefs_config)
    loaded = load_prefs(prefs_config)
    assert loaded.delete_senders == ["spam@example.com"]
    assert loaded.keep_senders == ["boss@company.com"]
    assert loaded.vip_senders == ["ceo@company.com"]
    assert loaded.boost_keywords == ["invoice", "urgent"]
    assert loaded.sender_reputation["spam@example.com"].delete == 3
    assert loaded.notes == "Test note"


def test_extract_sender_email_from_display_name():
    assert extract_sender_email("Jane Doe <jane@example.com>") == "jane@example.com"


def test_record_delete_adds_sender(prefs_config):
    record_delete("spam@example.com", config=prefs_config)
    prefs = load_prefs(prefs_config)
    assert "spam@example.com" in prefs.delete_senders
    assert prefs.sender_reputation["spam@example.com"].delete == 1


def test_record_keep_adds_to_protected_after_two(prefs_config):
    record_keep("boss@company.com", config=prefs_config)
    record_keep("boss@company.com", config=prefs_config)
    prefs = load_prefs(prefs_config)
    assert "boss@company.com" in prefs.keep_senders
    assert is_protected_sender("boss@company.com", prefs)


def test_record_vip_adds_and_clears_low_value(prefs_config):
    prefs = GmailPrefs(delete_senders=["vip@example.com"])
    save_prefs(prefs, prefs_config)
    record_vip("VIP Person <vip@example.com>", config=prefs_config)
    updated = load_prefs(prefs_config)
    assert "vip@example.com" in updated.vip_senders
    assert "vip@example.com" not in updated.delete_senders


def test_record_low_value_removes_vip_and_protected(prefs_config):
    prefs = GmailPrefs(
        vip_senders=["spam@example.com"],
        keep_senders=["spam@example.com"],
    )
    save_prefs(prefs, prefs_config)
    record_low_value("spam@example.com", config=prefs_config)
    updated = load_prefs(prefs_config)
    assert "spam@example.com" in updated.delete_senders
    assert "spam@example.com" not in updated.vip_senders
    assert "spam@example.com" not in updated.keep_senders


def test_is_vip_sender():
    prefs = GmailPrefs(vip_senders=["vip@example.com"])
    assert is_vip_sender("VIP Person <vip@example.com>", prefs)


def test_prefs_to_context_includes_vip_and_keywords():
    prefs = GmailPrefs(vip_senders=["vip@x.com"], boost_keywords=["invoice"])
    ctx = prefs_to_context(prefs)
    assert "vip@x.com" in ctx
    assert "invoice" in ctx


def test_prefs_to_context_empty_returns_empty():
    assert prefs_to_context(GmailPrefs()) == ""
