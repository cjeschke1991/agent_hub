from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from agent_hub.agents.daily_briefing.logic import get_briefing_status
from agent_hub.agents.priorities.logic import (
    load_priorities_yaml,
    save_priorities_yaml,
    write_priorities_slice,
)
from agent_hub.core.config import load_config
from agent_hub.core.paths import latest_briefing_path, priorities_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_TIMEOUT_SECONDS = 120


def _run_cli(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_SECONDS,
        check=False,
    )


def _python_command(*args: str) -> list[str]:
    return [sys.executable, "-m", *args]


def _status_emoji(status: str) -> str:
    return {
        "ok": "✅",
        "stale": "⚠️",
        "error": "❌",
        "missing": "⬜",
    }.get(status, "⬜")


def render() -> None:
    config = load_config()
    status = get_briefing_status(config)
    latest_path = latest_briefing_path(config.data_dir)

    header_col, refresh_col = st.columns([4, 1])
    with header_col:
        st.subheader("Daily Briefing")
        if status.assembled_at:
            st.caption(f"Last assembled: {status.assembled_at}")
    with refresh_col:
        if st.button("Refresh", use_container_width=True):
            with st.spinner("Assembling briefing..."):
                result = _run_cli(
                    _python_command("agent_hub.agents.daily_briefing.cli", "assemble", "--force")
                )
            if result.returncode == 0:
                st.success(result.stdout.strip() or "Briefing refreshed.")
                st.rerun()
            st.error(result.stderr.strip() or result.stdout.strip() or "Refresh failed.")

    st.markdown("#### Slice status")
    chip_cols = st.columns(len(status.slices) or 1)
    for column, slice_status in zip(chip_cols, status.slices):
        with column:
            st.markdown(
                f"{_status_emoji(slice_status['status'])} **{slice_status['title']}** — "
                f"`{slice_status['status']}`"
            )
            if slice_status["message"]:
                st.caption(slice_status["message"])

    st.divider()

    if latest_path.exists():
        st.markdown(latest_path.read_text(encoding="utf-8"))
    else:
        st.info("No briefing yet. Click Refresh to assemble one.")

    with st.expander("Edit priorities"):
        priorities_path = priorities_file(config.data_dir)
        priorities_path.parent.mkdir(parents=True, exist_ok=True)
        if not priorities_path.exists():
            write_priorities_slice(config)

        current_yaml = priorities_path.read_text(encoding="utf-8")
        edited_yaml = st.text_area("priorities.yaml", value=current_yaml, height=220)
        if st.button("Save priorities and update slice"):
            save_priorities_yaml(config.data_dir, edited_yaml)
            try:
                load_priorities_yaml(config.data_dir)
            except Exception as exc:
                st.error(f"Invalid YAML: {exc}")
            else:
                write_priorities_slice(config)
                st.success("Priorities slice updated.")
                st.rerun()
