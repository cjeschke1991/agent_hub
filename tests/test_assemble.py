from pathlib import Path

import pytest

from agent_hub.agents.daily_briefing.logic import assemble_briefing
from agent_hub.agents.gmail_stub.logic import write_gmail_stub_slice
from agent_hub.agents.priorities.logic import write_priorities_slice
from agent_hub.core.config import BriefingConfig, HubConfig
from agent_hub.core.paths import latest_briefing_path


def _config(data_dir: Path) -> HubConfig:
    return HubConfig(
        data_dir=data_dir,
        slice_order=["priorities", "gmail_stub"],
        stale_hours={"default": 36},
        briefing=BriefingConfig(title="Daily Briefing"),
    )


def test_assemble_writes_latest_markdown(tmp_path: Path):
    config = _config(tmp_path)
    write_priorities_slice(config)
    write_gmail_stub_slice(config)

    result = assemble_briefing(config)

    latest = latest_briefing_path(tmp_path)
    assert latest.exists()
    content = latest.read_text(encoding="utf-8")
    assert "Today's Priorities" in content
    assert "Inbox (stub)" in content
    assert result.overall_status == "ok"
