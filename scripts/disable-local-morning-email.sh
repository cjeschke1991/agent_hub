#!/usr/bin/env bash
# Disable the local 7am launchd job (use when switching to Google Apps Script).
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.agenthub.morning-email.plist"
USER_ID="$(id -u)"

if [[ -f "$PLIST" ]]; then
  launchctl bootout "gui/$USER_ID" "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed local morning-email launchd job."
else
  echo "No launchd job found at $PLIST"
fi

echo "Use scripts/google-apps-script-morning-email.js for cloud delivery at 7am."
