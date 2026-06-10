from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_hub.core.paths import PROJECT_ROOT, resolve_data_dir


@dataclass
class BriefingConfig:
    title: str = "Daily Briefing"


@dataclass
class HubConfig:
    data_dir: Path
    slice_order: list[str] = field(default_factory=list)
    stale_hours: dict[str, Any] = field(default_factory=dict)
    briefing: BriefingConfig = field(default_factory=BriefingConfig)

    def stale_threshold_hours(self, agent_id: str) -> float:
        default = self.stale_hours.get("default", 36)
        return float(self.stale_hours.get(agent_id, default))


def load_config(config_path: Path | None = None) -> HubConfig:
    path = config_path or (PROJECT_ROOT / "config.yaml")
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

    briefing_raw = raw.get("briefing", {}) or {}
    return HubConfig(
        data_dir=resolve_data_dir(raw.get("data_dir", "data")),
        slice_order=list(raw.get("slice_order", [])),
        stale_hours=dict(raw.get("stale_hours", {})),
        briefing=BriefingConfig(title=briefing_raw.get("title", "Daily Briefing")),
    )
