"""Simple JSON-based preference store that the LLM reads as context.

The file lives at <data_dir>/gmail_prefs.json and contains:
{
  "delete_senders": ["noreply@foo.com", ...],
  "keep_senders": ["important@example.com", ...],
  "delete_subjects": ["unsubscribe", ...],
  "notes": "Free-text preference notes the user has added."
}
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent_hub.core.config import HubConfig, load_config


@dataclass
class GmailPrefs:
    delete_senders: list[str] = field(default_factory=list)
    keep_senders: list[str] = field(default_factory=list)
    delete_subjects: list[str] = field(default_factory=list)
    notes: str = ""


def _prefs_path(config: HubConfig) -> Path:
    return Path(config.data_dir) / "gmail_prefs.json"


def load_prefs(config: HubConfig | None = None) -> GmailPrefs:
    cfg = config or load_config()
    path = _prefs_path(cfg)
    if not path.exists():
        return GmailPrefs()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return GmailPrefs(
            delete_senders=list(raw.get("delete_senders", [])),
            keep_senders=list(raw.get("keep_senders", [])),
            delete_subjects=list(raw.get("delete_subjects", [])),
            notes=str(raw.get("notes", "")),
        )
    except Exception:
        return GmailPrefs()


def save_prefs(prefs: GmailPrefs, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    path = _prefs_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(prefs), indent=2), encoding="utf-8")


def prefs_to_context(prefs: GmailPrefs) -> str:
    """Format prefs as a short text block the LLM can understand."""
    lines: list[str] = []
    if prefs.delete_senders:
        lines.append("Always delete emails from: " + ", ".join(prefs.delete_senders))
    if prefs.keep_senders:
        lines.append("Never delete emails from: " + ", ".join(prefs.keep_senders))
    if prefs.delete_subjects:
        lines.append(
            "Delete emails whose subject contains: " + ", ".join(prefs.delete_subjects)
        )
    if prefs.notes:
        lines.append("Additional notes: " + prefs.notes)
    return "\n".join(lines)


def record_delete(sender: str, config: HubConfig | None = None) -> None:
    """Teach the assistant that emails from *sender* should be deleted."""
    cfg = config or load_config()
    prefs = load_prefs(cfg)
    sender = sender.strip().lower()
    if sender and sender not in prefs.delete_senders:
        prefs.delete_senders.append(sender)
    if sender in prefs.keep_senders:
        prefs.keep_senders.remove(sender)
    save_prefs(prefs, cfg)


def record_keep(sender: str, config: HubConfig | None = None) -> None:
    """Teach the assistant that emails from *sender* should NOT be deleted."""
    cfg = config or load_config()
    prefs = load_prefs(cfg)
    sender = sender.strip().lower()
    if sender and sender not in prefs.keep_senders:
        prefs.keep_senders.append(sender)
    if sender in prefs.delete_senders:
        prefs.delete_senders.remove(sender)
    save_prefs(prefs, cfg)
