import typer

from agent_hub.agents.priorities.logic import write_priorities_slice

app = typer.Typer(help="Write today's priorities slice for the daily briefing.")


@app.command("write-slice")
def write_slice_cmd() -> None:
    write_priorities_slice()
    typer.echo("Priorities slice written.")


@app.command("version")
def version_cmd() -> None:
    typer.echo("priorities agent 0.1.0")


if __name__ == "__main__":
    app()
