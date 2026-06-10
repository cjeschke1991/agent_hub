from __future__ import annotations

from pathlib import Path

import yaml

from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.db import Database
from agent_hub.core.logging import get_logger
from agent_hub.core.paths import priorities_file
from agent_hub.core.slices import Slice, SliceItem, utc_now_iso, write_slice

AGENT_ID = "priorities"
DEFAULT_PRIORITIES = """title: Today's Priorities
items:
  - text: Review morning briefing
    detail: Check slice status and refresh if needed
  - text: Ship one agent hub improvement
    detail: Keep v1 momentum going
"""


def ensure_priorities_file(data_dir: Path) -> Path:
    path = priorities_file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(DEFAULT_PRIORITIES, encoding="utf-8")
    return path


def load_priorities_yaml(data_dir: Path) -> dict:
    path = ensure_priorities_file(data_dir)
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_priorities_yaml(data_dir: Path, content: str) -> Path:
    path = priorities_file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def build_slice_from_yaml(data: dict) -> Slice:
    items = [
        SliceItem(text=str(item.get("text", "")), detail=str(item.get("detail", "")))
        for item in data.get("items", [])
        if item.get("text")
    ]
    return Slice(
        agent_id=AGENT_ID,
        generated_at=utc_now_iso(),
        title=str(data.get("title", "Today's Priorities")),
        summary=str(data.get("summary", "")),
        items=items,
        status="ok",
    )


def write_priorities_slice(config: HubConfig | None = None) -> Slice:
    config = config or load_config()
    logger = get_logger(AGENT_ID, config.data_dir)
    db = Database(config.data_dir)

    try:
        data = load_priorities_yaml(config.data_dir)
        slice_data = build_slice_from_yaml(data)
        write_slice(config.data_dir, slice_data)
        db.record_slice_run(AGENT_ID, "ok")
        logger.info("Wrote priorities slice with %s items", len(slice_data.items))
        return slice_data
    except Exception as exc:
        error_slice = Slice(
            agent_id=AGENT_ID,
            generated_at=utc_now_iso(),
            title="Today's Priorities",
            summary="",
            status="error",
            message=str(exc),
        )
        write_slice(config.data_dir, error_slice)
        db.record_slice_run(AGENT_ID, "error", str(exc))
        logger.exception("Failed to write priorities slice")
        raise
