from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from agent_hub.core.config import HubConfig
from agent_hub.core.slices import Slice


@dataclass
class RenderedSlice:
    agent_id: str
    effective_status: str
    slice: Slice | None
    message: str = ""


@dataclass
class BriefingRenderResult:
    markdown: str
    overall_status: str
    rendered_slices: list[RenderedSlice]


def _parse_generated_at(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def effective_status(slice_data: Slice | None, stale_hours: float) -> tuple[str, str]:
    if slice_data is None:
        return "missing", "Not configured yet"
    if slice_data.status == "error":
        return "error", slice_data.message or "Producer reported an error"
    generated_at = _parse_generated_at(slice_data.generated_at)
    if generated_at is None:
        return "error", "Invalid generated_at timestamp"
    age_hours = (datetime.now(timezone.utc) - generated_at).total_seconds() / 3600
    if age_hours > stale_hours:
        return "stale", f"Last updated {age_hours:.1f} hours ago"
    return "ok", ""


def status_emoji(status: str) -> str:
    return {
        "ok": "✅",
        "stale": "⚠️",
        "error": "❌",
        "missing": "⬜",
    }.get(status, "⬜")


def render_briefing(
    config: HubConfig,
    slices: dict[str, Slice | None],
    assembled_at: str | None = None,
) -> BriefingRenderResult:
    assembled_at = assembled_at or datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {config.briefing.title}",
        "",
        f"_Assembled {assembled_at}_",
        "",
    ]

    rendered_slices: list[RenderedSlice] = []
    has_issue = False

    for agent_id in config.slice_order:
        slice_data = slices.get(agent_id)
        threshold = config.stale_threshold_hours(agent_id)
        status, message = effective_status(slice_data, threshold)
        rendered = RenderedSlice(
            agent_id=agent_id,
            effective_status=status,
            slice=slice_data,
            message=message,
        )
        rendered_slices.append(rendered)

        if status in {"error", "stale", "missing"}:
            has_issue = True

        lines.append(f"## {status_emoji(status)} {slice_data.title if slice_data else agent_id}")
        lines.append("")

        if slice_data is None:
            lines.append("_Not configured yet._")
            lines.append("")
            continue

        if slice_data.summary:
            lines.append(slice_data.summary)
            lines.append("")

        if status != "ok" and message:
            lines.append(f"_{message}_")
            lines.append("")

        if slice_data.items:
            for item in slice_data.items:
                if item.detail:
                    lines.append(f"- **{item.text}** — {item.detail}")
                else:
                    lines.append(f"- {item.text}")
            lines.append("")
        elif status == "ok":
            lines.append("_No items._")
            lines.append("")

    overall_status = "partial" if has_issue else "ok"
    return BriefingRenderResult(
        markdown="\n".join(lines).rstrip() + "\n",
        overall_status=overall_status,
        rendered_slices=rendered_slices,
    )
