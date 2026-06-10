from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent_hub.core.config import BriefingConfig, HubConfig
from agent_hub.core.render import render_briefing
from agent_hub.core.slices import Slice, SliceItem


def _config() -> HubConfig:
    return HubConfig(
        data_dir=Path("/tmp/agent-hub-test"),
        slice_order=["priorities", "gmail_stub"],
        stale_hours={"default": 36},
        briefing=BriefingConfig(title="Daily Briefing"),
    )


def test_render_includes_ok_and_missing_sections():
    now = datetime.now(timezone.utc).isoformat()
    slices = {
        "priorities": Slice(
            agent_id="priorities",
            generated_at=now,
            title="Today's Priorities",
            summary="Focus items",
            items=[SliceItem(text="Ship v1", detail="Agent hub")],
            status="ok",
        ),
        "gmail_stub": None,
    }

    result = render_briefing(_config(), slices, assembled_at=now)

    assert "Today's Priorities" in result.markdown
    assert "Ship v1" in result.markdown
    assert "Not configured yet" in result.markdown
    assert "Inbox" not in result.markdown
    assert result.overall_status == "partial"


def test_render_marks_stale_slice():
    old = (datetime.now(timezone.utc) - timedelta(hours=40)).isoformat()
    slices = {
        "priorities": Slice(
            agent_id="priorities",
            generated_at=old,
            title="Today's Priorities",
            summary="",
            status="ok",
        ),
        "gmail_stub": Slice(
            agent_id="gmail_stub",
            generated_at=old,
            title="Inbox",
            summary="",
            status="ok",
        ),
    }

    result = render_briefing(_config(), slices)

    assert result.overall_status == "partial"
    assert any(item.effective_status == "stale" for item in result.rendered_slices)
