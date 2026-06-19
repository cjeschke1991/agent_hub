from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_hub.agents.gmail_assistant.prefs import (
    GmailPrefs,
    load_prefs,
    prefs_to_context,
    record_delete,
    record_keep,
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
    assert prefs.notes == ""


def test_save_and_load_roundtrip(prefs_config):
    prefs = GmailPrefs(
        delete_senders=["spam@example.com"],
        keep_senders=["boss@company.com"],
        delete_subjects=["unsubscribe"],
        notes="Test note",
    )
    save_prefs(prefs, prefs_config)
    loaded = load_prefs(prefs_config)
    assert loaded.delete_senders == ["spam@example.com"]
    assert loaded.keep_senders == ["boss@company.com"]
    assert loaded.delete_subjects == ["unsubscribe"]
    assert loaded.notes == "Test note"


def test_record_delete_adds_sender(prefs_config):
    record_delete("spam@example.com", config=prefs_config)
    prefs = load_prefs(prefs_config)
    assert "spam@example.com" in prefs.delete_senders


def test_record_delete_removes_from_keep(prefs_config):
    prefs = GmailPrefs(keep_senders=["flip@example.com"])
    save_prefs(prefs, prefs_config)
    record_delete("flip@example.com", config=prefs_config)
    updated = load_prefs(prefs_config)
    assert "flip@example.com" not in updated.keep_senders
    assert "flip@example.com" in updated.delete_senders


def test_record_keep_removes_from_delete(prefs_config):
    prefs = GmailPrefs(delete_senders=["flip@example.com"])
    save_prefs(prefs, prefs_config)
    record_keep("flip@example.com", config=prefs_config)
    updated = load_prefs(prefs_config)
    assert "flip@example.com" not in updated.delete_senders
    assert "flip@example.com" in updated.keep_senders


def test_prefs_to_context_formats_correctly():
    prefs = GmailPrefs(
        delete_senders=["spam@x.com"],
        keep_senders=["vip@x.com"],
        delete_subjects=["newsletter"],
        notes="My note",
    )
    ctx = prefs_to_context(prefs)
    assert "spam@x.com" in ctx
    assert "vip@x.com" in ctx
    assert "newsletter" in ctx
    assert "My note" in ctx


def test_prefs_to_context_empty_returns_empty():
    assert prefs_to_context(GmailPrefs()) == ""
