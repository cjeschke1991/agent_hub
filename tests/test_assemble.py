from agent_hub.agents.daily_briefing.logic import assemble_briefing
from agent_hub.agents.gmail_stub.logic import write_gmail_stub_slice
from agent_hub.agents.priorities.logic import write_priorities_slice
from agent_hub.core.paths import latest_briefing_path


def test_assemble_writes_latest_markdown(briefing_config):
    write_priorities_slice(briefing_config)
    write_gmail_stub_slice(briefing_config)

    result = assemble_briefing(briefing_config)

    latest = latest_briefing_path(briefing_config.data_dir)
    assert latest.exists()
    content = latest.read_text(encoding="utf-8")
    assert "Today's Priorities" in content
    assert "Inbox (stub)" in content
    assert result.overall_status == "ok"
