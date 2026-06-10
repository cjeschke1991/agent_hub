import json

import typer

from agent_hub.agents.pinball_tracker.logic import export_status
from agent_hub.agents.pinball_tracker.seed import seed_collection
from agent_hub.core.pinball_db import init_db

app = typer.Typer(help="Pinball Tracker database and status commands.")


@app.command("init-db")
def init_db_cmd() -> None:
    path = init_db()
    typer.echo(f"Pinball database ready: {path}")


@app.command("export-status")
def export_status_cmd() -> None:
    typer.echo(json.dumps(export_status(), indent=2))


@app.command("seed-collection")
def seed_collection_cmd(
    force_images: bool = typer.Option(False, "--force-images", help="Re-download cabinet images."),
) -> None:
    result = seed_collection(force_refresh_images=force_images)
    typer.echo(
        f"Seed complete: created={result.created}, updated={result.updated}, "
        f"skipped={result.skipped}, images={result.images_downloaded}"
    )


@app.command("version")
def version_cmd() -> None:
    typer.echo("pinball tracker 0.1.0")


if __name__ == "__main__":
    app()
