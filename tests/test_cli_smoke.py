import json
from pathlib import Path

import pytest

from agent_hub.agents.daily_briefing.logic import assemble_briefing, status_as_json
from agent_hub.agents.gmail_stub.logic import write_gmail_stub_slice
from agent_hub.agents.priorities.logic import write_priorities_slice
from agent_hub.core.config import BriefingConfig, HubConfig


def _config(data_dir: Path) -> HubConfig:
    return HubConfig(
        data_dir=data_dir,
        slice_order=["priorities", "gmail_stub"],
        stale_hours={"default": 36},
        briefing=BriefingConfig(title="Daily Briefing"),
    )


@pytest.mark.integration
def test_status_json_after_morning_chain(tmp_path: Path):
    config = _config(tmp_path)
    write_priorities_slice(config)
    write_gmail_stub_slice(config)
    assemble_briefing(config)

    payload = json.loads(status_as_json(config))
    assert payload["overall_status"] == "ok"
    assert len(payload["slices"]) == 2
    assert payload["assembled_at"] is not None
