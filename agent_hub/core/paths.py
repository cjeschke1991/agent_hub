from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_data_dir(data_dir: str | Path | None = None) -> Path:
    if data_dir is None:
        return PROJECT_ROOT / "data"
    path = Path(data_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def slices_dir(data_dir: Path) -> Path:
    return data_dir / "slices"


def briefings_dir(data_dir: Path) -> Path:
    return data_dir / "briefings"


def logs_dir(data_dir: Path) -> Path:
    return data_dir / "logs"


def priorities_file(data_dir: Path) -> Path:
    return data_dir / "priorities.yaml"


def slice_path(data_dir: Path, agent_id: str) -> Path:
    return slices_dir(data_dir) / agent_id / "latest.json"


def slice_body_path(data_dir: Path, agent_id: str) -> Path:
    return slices_dir(data_dir) / agent_id / "body.md"


def latest_briefing_path(data_dir: Path) -> Path:
    return briefings_dir(data_dir) / "latest.md"


def dated_briefing_path(data_dir: Path, date_str: str) -> Path:
    return briefings_dir(data_dir) / f"{date_str}.md"


def lock_path(data_dir: Path) -> Path:
    return data_dir / ".briefing.lock"
