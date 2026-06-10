import json

import pytest

from agent_hub.agents.daily_briefing.logic import assemble_briefing, status_as_json
from agent_hub.agents.gmail_stub.logic import write_gmail_stub_slice
from agent_hub.agents.priorities.logic import write_priorities_slice


@pytest.mark.integration
def test_status_json_after_morning_chain(briefing_config):
    write_priorities_slice(briefing_config)
    write_gmail_stub_slice(briefing_config)
    assemble_briefing(briefing_config)

    payload = json.loads(status_as_json(briefing_config))
    assert payload["overall_status"] == "ok"
    assert len(payload["slices"]) == 2
    assert payload["assembled_at"] is not None
