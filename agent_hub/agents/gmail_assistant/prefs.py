"""Preference store and sender reputation for the Gmail Assistant."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent_hub.core.config import HubConfig, load_config


@dataclass
class SenderReputation:
    keep: int = 0
    delete: int = 0


@dataclass
class GmailPrefs:
    delete_senders: list[str] = field(default_factory=list)
    keep_senders: list[str] = field(default_factory=list)
    vip_senders: list[str] = field(default_factory=list)
    delete_subjects: list[str] = field(default_factory=list)
    boost_keywords: list[str] = field(default_factory=list)
    sender_reputation: dict[str, SenderReputation] = field(default_factory=dict)
    notes: str = ""


def _prefs_path(config: HubConfig) -> Path:
    return Path(config.data_dir) / "gmail_prefs.json"


def _parse_reputation(raw: dict) -> dict[str, SenderReputation]:
    result: dict[str, SenderReputation] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            result[key.lower()] = SenderReputation(
                keep=int(value.get("keep", 0)),
                delete=int(value.get("delete", 0)),
            )
    return result


def _reputation_to_json(reputation: dict[str, SenderReputation]) -> dict[str, dict[str, int]]:
    return {key: {"keep": rep.keep, "delete": rep.delete} for key, rep in reputation.items()}


def load_prefs(config: HubConfig | None = None) -> GmailPrefs:
    cfg = config or load_config()
    path = _prefs_path(cfg)
    if not path.exists():
        return GmailPrefs()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return GmailPrefs(
            delete_senders=[s.lower() for s in raw.get("delete_senders", [])],
            keep_senders=[s.lower() for s in raw.get("keep_senders", [])],
            vip_senders=[s.lower() for s in raw.get("vip_senders", [])],
            delete_subjects=list(raw.get("delete_subjects", [])),
            boost_keywords=list(raw.get("boost_keywords", [])),
            sender_reputation=_parse_reputation(raw.get("sender_reputation", {})),
            notes=str(raw.get("notes", "")),
        )
    except Exception:
        return GmailPrefs()


def save_prefs(prefs: GmailPrefs, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    path = _prefs_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(prefs)
    payload["sender_reputation"] = _reputation_to_json(prefs.sender_reputation)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def extract_sender_email(sender: str) -> str:
    match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", sender.lower())
    return match.group(0) if match else sender.lower().strip()


def sender_matches_list(sender: str, entries: list[str]) -> bool:
    email = extract_sender_email(sender)
    sender_lower = sender.lower()
    for entry in entries:
        needle = entry.lower().strip()
        if not needle:
            continue
        if needle == email or needle in email or needle in sender_lower:
            return True
    return False


def is_vip_sender(sender: str, prefs: GmailPrefs) -> bool:
    return sender_matches_list(sender, prefs.vip_senders)


def is_protected_sender(sender: str, prefs: GmailPrefs) -> bool:
    if sender_matches_list(sender, prefs.keep_senders):
        return True
    if is_vip_sender(sender, prefs):
        return True
    email = extract_sender_email(sender)
    rep = prefs.sender_reputation.get(email)
    return rep is not None and rep.keep >= 2


def get_sender_reputation(sender: str, prefs: GmailPrefs) -> SenderReputation:
    email = extract_sender_email(sender)
    return prefs.sender_reputation.get(email, SenderReputation())


def prefs_to_context(prefs: GmailPrefs, calendar_context: str = "") -> str:
    lines: list[str] = []
    if prefs.vip_senders:
        lines.append("VIP senders (always high importance, never delete): " + ", ".join(prefs.vip_senders))
    if prefs.keep_senders:
        lines.append("Protected senders (never delete): " + ", ".join(prefs.keep_senders))
    if prefs.delete_senders:
        lines.append("Low-value senders (safe to delete): " + ", ".join(prefs.delete_senders))
    if prefs.boost_keywords:
        lines.append("Important keywords (boost urgency): " + ", ".join(prefs.boost_keywords))
    if prefs.delete_subjects:
        lines.append("Delete if subject contains: " + ", ".join(prefs.delete_subjects))
    if prefs.notes:
        lines.append("Additional notes: " + prefs.notes)
    if calendar_context:
        lines.append(calendar_context)
    return "\n".join(lines)


def _bump_reputation(sender: str, prefs: GmailPrefs, *, keep: bool) -> None:
    email = extract_sender_email(sender)
    rep = prefs.sender_reputation.setdefault(email, SenderReputation())
    if keep:
        rep.keep += 1
        if rep.keep >= 2 and email not in prefs.keep_senders:
            prefs.keep_senders.append(email)
    else:
        rep.delete += 1


def record_vip(sender: str, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    prefs = load_prefs(cfg)
    sender_key = extract_sender_email(sender)
    if sender_key and sender_key not in prefs.vip_senders:
        prefs.vip_senders.append(sender_key)
    if sender_key in prefs.delete_senders:
        prefs.delete_senders.remove(sender_key)
    save_prefs(prefs, cfg)


def record_protected(sender: str, config: HubConfig | None = None) -> None:
    """Add sender to the protected (never delete) list."""
    record_keep(sender, config=config)


def record_low_value(sender: str, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    prefs = load_prefs(cfg)
    sender_key = extract_sender_email(sender)
    if sender_key and sender_key not in prefs.delete_senders:
        prefs.delete_senders.append(sender_key)
    if sender_key in prefs.keep_senders:
        prefs.keep_senders.remove(sender_key)
    if sender_key in prefs.vip_senders:
        prefs.vip_senders.remove(sender_key)
    _bump_reputation(sender, prefs, keep=False)
    save_prefs(prefs, cfg)


def record_delete(sender: str, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    prefs = load_prefs(cfg)
    sender_key = extract_sender_email(sender)
    if sender_key and sender_key not in prefs.delete_senders:
        prefs.delete_senders.append(sender_key)
    if sender_key in prefs.keep_senders:
        prefs.keep_senders.remove(sender_key)
    _bump_reputation(sender, prefs, keep=False)
    save_prefs(prefs, cfg)


def record_keep(sender: str, config: HubConfig | None = None) -> None:
    cfg = config or load_config()
    prefs = load_prefs(cfg)
    sender_key = extract_sender_email(sender)
    if sender_key and sender_key not in prefs.keep_senders:
        prefs.keep_senders.append(sender_key)
    if sender_key in prefs.delete_senders:
        prefs.delete_senders.remove(sender_key)
    _bump_reputation(sender, prefs, keep=True)
    save_prefs(prefs, cfg)
