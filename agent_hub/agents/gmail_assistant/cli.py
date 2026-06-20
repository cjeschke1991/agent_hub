from __future__ import annotations

import typer

from agent_hub.agents.gmail_assistant.auth import gmail_credentials_configured
from agent_hub.agents.gmail_assistant.logic import send_morning_email
from agent_hub.core.config import load_config

app = typer.Typer(help="Gmail Assistant commands.")


@app.command("send-morning-email")
def send_morning_email_cmd(
    to: str | None = typer.Option(
        None,
        "--to",
        help="Override recipient (useful for testing before the real 7am send).",
    ),
) -> None:
    """Send the daily good-morning email configured in config.yaml."""
    config = load_config()
    if not gmail_credentials_configured(config):
        typer.echo(
            "Gmail credentials not configured. Set GMAIL_CREDENTIALS_PATH in .env.",
            err=True,
        )
        raise typer.Exit(code=1)

    morning = config.gmail.morning_email
    if to is None and not morning.enabled:
        typer.echo(
            "Morning email is disabled (gmail.morning_email.enabled: false in config.yaml).",
            err=True,
        )
        raise typer.Exit(code=1)
    recipient = (to or morning.to).strip()
    try:
        message_id = send_morning_email(config, to=to)
    except Exception as exc:
        typer.echo(f"Failed to send morning email: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    label = "test send" if to else "morning email"
    typer.echo(f"Sent {label} to {recipient} (message id: {message_id}).")


@app.command("status")
def status_cmd() -> None:
    """Show morning email configuration."""
    config = load_config()
    morning = config.gmail.morning_email
    creds_ok = gmail_credentials_configured(config)
    typer.echo(f"Gmail credentials: {'configured' if creds_ok else 'missing'}")
    typer.echo(f"Morning email enabled: {morning.enabled}")
    typer.echo(f"Morning email to: {morning.to or '(not set)'}")
    typer.echo(f"Subject: {morning.subject}")
    typer.echo(f"Body: {morning.body}")


if __name__ == "__main__":
    app()
