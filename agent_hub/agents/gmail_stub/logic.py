from __future__ import annotations

from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.db import Database
from agent_hub.core.logging import get_logger
from agent_hub.core.slices import Slice, SliceItem, utc_now_iso, write_slice

AGENT_ID = "gmail_stub"


def build_stub_slice() -> Slice:
    return Slice(
        agent_id=AGENT_ID,
        generated_at=utc_now_iso(),
        title="Inbox (stub)",
        summary="Stub producer until the Gmail assistant tab ships.",
        items=[
            SliceItem(text="2 messages flagged follow-up", detail="Replace with live Gmail agent"),
            SliceItem(text="1 calendar-related thread", detail="Demo data only"),
        ],
        status="ok",
    )


def write_gmail_stub_slice(config: HubConfig | None = None) -> Slice:
    config = config or load_config()
    logger = get_logger(AGENT_ID, config.data_dir)
    db = Database(config.data_dir)

    try:
        slice_data = build_stub_slice()
        write_slice(config.data_dir, slice_data)
        db.record_slice_run(AGENT_ID, "ok")
        logger.info("Wrote gmail stub slice")
        return slice_data
    except Exception as exc:
        error_slice = Slice(
            agent_id=AGENT_ID,
            generated_at=utc_now_iso(),
            title="Inbox (stub)",
            summary="",
            status="error",
            message=str(exc),
        )
        write_slice(config.data_dir, error_slice)
        db.record_slice_run(AGENT_ID, "error", str(exc))
        logger.exception("Failed to write gmail stub slice")
        raise
