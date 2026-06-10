import subprocess
import sys

import typer

from agent_hub.agents.daily_briefing.logic import (
    assemble_briefing,
    open_latest_briefing,
    status_as_json,
)
from agent_hub.core.lock import BriefingLockError

app = typer.Typer(help="Assemble and inspect the daily briefing.")


@app.command("assemble")
def assemble_cmd(force: bool = typer.Option(False, "--force", help="Force a new assemble run.")) -> None:
    try:
        result = assemble_briefing(force=force)
        typer.echo(f"Briefing assembled: {result.path} ({result.overall_status})")
    except BriefingLockError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command("status")
def status_cmd() -> None:
    typer.echo(status_as_json())


@app.command("open")
def open_cmd() -> None:
    path = open_latest_briefing()
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    typer.echo(f"Opened {path}")


if __name__ == "__main__":
    app()
