#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
TO="${1:-}"

cd "$ROOT"
if [[ -n "$TO" ]]; then
  exec "$PYTHON" -m agent_hub.agents.gmail_assistant.cli send-morning-email --to "$TO"
fi
exec "$PYTHON" -m agent_hub.agents.gmail_assistant.cli send-morning-email
