from pathlib import Path

import pytest

from agent_hub.agents.pinball_tracker.logic import list_machines
from agent_hub.agents.pinball_tracker.seed import seed_collection
from agent_hub.agents.pinball_tracker.seed_catalog import COLLECTION_SEEDS


@pytest.mark.integration
def test_seed_collection_creates_machines_and_images(hub_config, monkeypatch: pytest.MonkeyPatch):
    def fake_download(url: str, destination: Path) -> bool:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake-image")
        return True

    monkeypatch.setattr("agent_hub.agents.pinball_tracker.seed._download_image", fake_download)

    first = seed_collection(hub_config)
    second = seed_collection(hub_config)

    machines = list_machines(hub_config)
    assert first.created == len(COLLECTION_SEEDS)
    assert second.skipped == len(COLLECTION_SEEDS)
    assert len(machines) == len(COLLECTION_SEEDS)
    assert all(machine.image_path for machine in machines)
    assert all(machine.rulesheet_url and "tiltforums.com" in machine.rulesheet_url for machine in machines)
    assert machines[0].ruleset
