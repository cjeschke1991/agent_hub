#!/usr/bin/env bash
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Morning Briefing
# @raycast.mode fullOutput
# @raycast.packageName Agent Hub

set -euo pipefail

ROOT_DIR="/Users/clayjeschke/cursor_projects/agent_hub"
PYTHON="$ROOT_DIR/.venv/bin/python"

cd "$ROOT_DIR"
"$PYTHON" -m agent_hub.agents.priorities.cli write-slice
"$PYTHON" -m agent_hub.agents.gmail_stub.cli write-slice
"$PYTHON" -m agent_hub.agents.daily_briefing.cli assemble --force
"$PYTHON" -m agent_hub.agents.daily_briefing.cli open
