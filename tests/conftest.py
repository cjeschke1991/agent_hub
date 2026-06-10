from pathlib import Path

import pytest

from agent_hub.core.config import BriefingConfig, HubConfig


@pytest.fixture
def hub_config(tmp_path: Path) -> HubConfig:
    return HubConfig(data_dir=tmp_path)


@pytest.fixture
def briefing_config(tmp_path: Path) -> HubConfig:
    return HubConfig(
        data_dir=tmp_path,
        slice_order=["priorities", "gmail_stub"],
        stale_hours={"default": 36},
        briefing=BriefingConfig(title="Daily Briefing"),
    )
