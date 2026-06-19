from __future__ import annotations

from agent_hub.agents.gmail_assistant.user_scores import (
    get_sender_stats,
    load_all_scores,
    load_score,
    save_score,
    sender_score_context,
)
from agent_hub.core.config import HubConfig


def test_save_and_load_score(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    save_score("msg1", "Boss <boss@company.com>", 8, subject="Q4 Review", config=config)
    assert load_score("msg1", config) == 8


def test_load_score_missing_returns_none(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    assert load_score("nonexistent", config) is None


def test_sender_stats_aggregates_multiple_scores(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    save_score("msg1", "boss@company.com", 8, config=config)
    save_score("msg2", "boss@company.com", 6, config=config)
    save_score("msg3", "boss@company.com", 10, config=config)
    stats = get_sender_stats("boss@company.com", config)
    assert stats is not None
    assert stats.count == 3
    assert abs(stats.avg - 8.0) < 0.01


def test_updating_score_replaces_old_value(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    save_score("msg1", "boss@company.com", 3, config=config)
    save_score("msg1", "boss@company.com", 9, config=config)
    assert load_score("msg1", config) == 9
    stats = get_sender_stats("boss@company.com", config)
    # Should contain only 9 (old 3 replaced).
    assert stats.scores == [9]


def test_sender_score_context_high(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    save_score("msg1", "boss@company.com", 9, config=config)
    ctx = sender_score_context("boss@company.com", config)
    assert "9.0/10" in ctx
    assert "important" in ctx


def test_sender_score_context_low(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    save_score("msg1", "spam@promo.com", 1, config=config)
    ctx = sender_score_context("spam@promo.com", config)
    assert "low importance" in ctx


def test_sender_score_context_missing_returns_empty(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    assert sender_score_context("unknown@example.com", config) == ""


def test_load_all_scores(tmp_path):
    config = HubConfig(data_dir=tmp_path)
    save_score("msg1", "a@x.com", 7, config=config)
    save_score("msg2", "b@x.com", 2, config=config)
    all_scores = load_all_scores(config)
    assert all_scores == {"msg1": 7, "msg2": 2}
