"""User-assigned importance scores for Gmail emails.

Scores are stored per message and aggregated per sender so that future emails
from the same sender carry the user's calibrated importance signal into the LLM
prompt.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_hub.agents.gmail_assistant.prefs import extract_sender_email
from agent_hub.core.config import HubConfig, load_config


@dataclass
class SenderScoreStats:
    scores: list[int] = field(default_factory=list)

    @property
    def avg(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def count(self) -> int:
        return len(self.scores)


def _scores_path(config: HubConfig) -> Path:
    return Path(config.data_dir) / "gmail_user_scores.json"


def _load_raw(config: HubConfig) -> dict[str, Any]:
    path = _scores_path(config)
    if not path.exists():
        return {"by_msg_id": {}, "by_sender": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"by_msg_id": {}, "by_sender": {}}


def _save_raw(data: dict[str, Any], config: HubConfig) -> None:
    path = _scores_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_score(
    msg_id: str,
    sender: str,
    score: int,
    *,
    subject: str = "",
    config: HubConfig | None = None,
) -> None:
    """Persist a user-assigned 0-10 score for a specific email."""
    cfg = config or load_config()
    data = _load_raw(cfg)
    sender_key = extract_sender_email(sender)

    prev = data["by_msg_id"].get(msg_id, {})
    prev_score = prev.get("score")

    data["by_msg_id"][msg_id] = {
        "score": int(score),
        "sender": sender_key,
        "subject": subject,
    }

    sender_entry = data["by_sender"].setdefault(sender_key, {"scores": []})
    scores: list[int] = sender_entry.get("scores", [])

    # Replace old score for this msg_id if it existed.
    if prev_score is not None and prev_score in scores:
        scores.remove(prev_score)
    scores.append(int(score))
    sender_entry["scores"] = scores

    _save_raw(data, cfg)


def load_score(msg_id: str, config: HubConfig | None = None) -> int | None:
    """Return the user-assigned score for a specific message, or None."""
    cfg = config or load_config()
    entry = _load_raw(cfg)["by_msg_id"].get(msg_id)
    return int(entry["score"]) if entry and "score" in entry else None


def get_sender_stats(sender: str, config: HubConfig | None = None) -> SenderScoreStats | None:
    """Return aggregate score stats for all emails from this sender, or None."""
    cfg = config or load_config()
    sender_key = extract_sender_email(sender)
    entry = _load_raw(cfg)["by_sender"].get(sender_key)
    if not entry or not entry.get("scores"):
        return None
    return SenderScoreStats(scores=list(entry["scores"]))


def sender_score_context(sender: str, config: HubConfig | None = None) -> str:
    """One-line string suitable for injecting into the LLM prompt."""
    stats = get_sender_stats(sender, config)
    if stats is None:
        return ""
    avg = stats.avg
    n = stats.count
    if avg >= 7:
        quality = "important"
    elif avg >= 4:
        quality = "moderately important"
    else:
        quality = "low importance"
    return (
        f"User feedback: rated {n} previous email(s) from this sender "
        f"avg {avg:.1f}/10 — treat as {quality}."
    )


def load_all_scores(config: HubConfig | None = None) -> dict[str, int]:
    """Return {msg_id: score} for every scored email."""
    cfg = config or load_config()
    raw = _load_raw(cfg)["by_msg_id"]
    return {mid: int(entry["score"]) for mid, entry in raw.items() if "score" in entry}
