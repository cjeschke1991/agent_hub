from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.db import Database
from agent_hub.core.lock import BriefingLockError, briefing_lock
from agent_hub.core.logging import get_logger
from agent_hub.core.paths import dated_briefing_path, latest_briefing_path, lock_path
from agent_hub.core.render import RenderedSlice, effective_status, render_briefing
from agent_hub.core.slices import Slice, read_slice

AGENT_ID = "daily_briefing"


@dataclass
class AssembleResult:
    briefing_date: str
    path: Path
    latest_path: Path
    overall_status: str
    rendered_slices: list[RenderedSlice]


@dataclass
class BriefingStatus:
    overall_status: str
    assembled_at: str | None
    briefing_path: str | None
    slices: list[dict]


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_slices_for_order(config: HubConfig) -> dict[str, Slice | None]:
    return {agent_id: read_slice(config.data_dir, agent_id) for agent_id in config.slice_order}


def assemble_briefing(config: HubConfig | None = None, force: bool = False) -> AssembleResult:
    config = config or load_config()
    logger = get_logger(AGENT_ID, config.data_dir)
    db = Database(config.data_dir)
    data_dir = config.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    lockfile = lock_path(data_dir)
    try:
        with briefing_lock(lockfile, force=force):
            slices = load_slices_for_order(config)
            assembled_at = datetime.now(timezone.utc).isoformat()
            rendered = render_briefing(config, slices, assembled_at=assembled_at)

            briefing_date = _today_str()
            dated_path = dated_briefing_path(data_dir, briefing_date)
            latest_path = latest_briefing_path(data_dir)
            dated_path.parent.mkdir(parents=True, exist_ok=True)

            dated_path.write_text(rendered.markdown, encoding="utf-8")
            latest_path.write_text(rendered.markdown, encoding="utf-8")

            db.upsert_briefing(
                briefing_date=briefing_date,
                path=str(dated_path),
                slice_count=len(rendered.rendered_slices),
                status=rendered.overall_status,
            )
            logger.info(
                "Assembled briefing for %s with status %s",
                briefing_date,
                rendered.overall_status,
            )
            return AssembleResult(
                briefing_date=briefing_date,
                path=dated_path,
                latest_path=latest_path,
                overall_status=rendered.overall_status,
                rendered_slices=rendered.rendered_slices,
            )
    except BriefingLockError:
        logger.warning("Briefing assemble skipped: lock held")
        raise


def get_briefing_status(config: HubConfig | None = None) -> BriefingStatus:
    config = config or load_config()
    db = Database(config.data_dir)
    slices = load_slices_for_order(config)

    slice_statuses = []
    has_issue = False
    for agent_id in config.slice_order:
        slice_data = slices.get(agent_id)
        threshold = config.stale_threshold_hours(agent_id)
        status, message = effective_status(slice_data, threshold)
        if status != "ok":
            has_issue = True
        slice_statuses.append(
            {
                "agent_id": agent_id,
                "status": status,
                "message": message,
                "title": slice_data.title if slice_data else agent_id,
                "generated_at": slice_data.generated_at if slice_data else None,
            }
        )

    latest = db.latest_briefing()
    overall = "partial" if has_issue else "ok"
    if latest and latest.status == "partial":
        overall = "partial"

    return BriefingStatus(
        overall_status=overall,
        assembled_at=latest.assembled_at if latest else None,
        briefing_path=latest.path if latest else None,
        slices=slice_statuses,
    )


def status_as_json(config: HubConfig | None = None) -> str:
    status = get_briefing_status(config)
    return json.dumps(asdict(status), indent=2)


def open_latest_briefing(config: HubConfig | None = None) -> Path:
    config = config or load_config()
    latest_path = latest_briefing_path(config.data_dir)
    if not latest_path.exists():
        assemble_briefing(config)
        latest_path = latest_briefing_path(config.data_dir)
    return latest_path
