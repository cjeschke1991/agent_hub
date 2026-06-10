#!/usr/bin/env bash
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Briefing Status
# @raycast.mode fullOutput
# @raycast.packageName Agent Hub

set -euo pipefail

ROOT_DIR="/Users/clayjeschke/cursor_projects/agent_hub"
PYTHON="$ROOT_DIR/.venv/bin/python"

cd "$ROOT_DIR"
"$PYTHON" -m agent_hub.agents.daily_briefing.cli status
