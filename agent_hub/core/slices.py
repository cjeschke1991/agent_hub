from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_hub.core.paths import slice_body_path, slice_path


SLICE_STATUSES = {"ok", "stale", "error"}


@dataclass
class SliceItem:
    text: str
    detail: str = ""


@dataclass
class Slice:
    agent_id: str
    generated_at: str
    title: str
    summary: str
    items: list[SliceItem] = field(default_factory=list)
    status: str = "ok"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Slice:
        items = [SliceItem(**item) for item in data.get("items", [])]
        return cls(
            agent_id=data["agent_id"],
            generated_at=data["generated_at"],
            title=data["title"],
            summary=data.get("summary", ""),
            items=items,
            status=data.get("status", "ok"),
            message=data.get("message", ""),
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_slice(data_dir: Path, slice_data: Slice, body_md: str | None = None) -> Path:
    destination = slice_path(data_dir, slice_data.agent_id)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temp_path = destination.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(slice_data.to_dict(), handle, indent=2)
        handle.write("\n")
    temp_path.replace(destination)

    if body_md is not None:
        body_destination = slice_body_path(data_dir, slice_data.agent_id)
        body_temp = body_destination.with_suffix(".md.tmp")
        body_temp.write_text(body_md, encoding="utf-8")
        body_temp.replace(body_destination)

    return destination


def read_slice(data_dir: Path, agent_id: str) -> Slice | None:
    path = slice_path(data_dir, agent_id)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return Slice.from_dict(json.load(handle))


def read_slice_body(data_dir: Path, agent_id: str) -> str | None:
    path = slice_body_path(data_dir, agent_id)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
