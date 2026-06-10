import json
from pathlib import Path

from agent_hub.core.slices import Slice, SliceItem, read_slice, write_slice


def test_write_slice_is_atomic(tmp_path: Path):
    slice_data = Slice(
        agent_id="priorities",
        generated_at="2026-06-10T12:00:00+00:00",
        title="Today's Priorities",
        summary="Test",
        items=[SliceItem(text="One", detail="Detail")],
        status="ok",
    )

    destination = write_slice(tmp_path, slice_data)
    loaded = read_slice(tmp_path, "priorities")

    assert destination.exists()
    assert loaded is not None
    assert loaded.title == "Today's Priorities"
    assert loaded.items[0].text == "One"

    raw = json.loads(destination.read_text(encoding="utf-8"))
    assert raw["agent_id"] == "priorities"
