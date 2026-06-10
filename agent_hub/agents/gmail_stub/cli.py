import typer

from agent_hub.agents.gmail_stub.logic import write_gmail_stub_slice

app = typer.Typer(help="Write a stub Gmail slice for the daily briefing.")


@app.command("write-slice")
def write_slice_cmd() -> None:
    write_gmail_stub_slice()
    typer.echo("Gmail stub slice written.")


@app.command("version")
def version_cmd() -> None:
    typer.echo("gmail-stub agent 0.1.0")


if __name__ == "__main__":
    app()
