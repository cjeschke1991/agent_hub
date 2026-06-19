from __future__ import annotations

from pathlib import Path

from agent_hub.core.config import GmailConfig, HubConfig, load_config

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

_DEFAULT_TOKEN_PATH = Path.home() / ".agent_hub" / "gmail_token.json"


def _token_path(config: GmailConfig) -> Path:
    if config.token_path:
        return Path(config.token_path)
    return _DEFAULT_TOKEN_PATH


def gmail_credentials_configured(config: HubConfig | None = None) -> bool:
    cfg = (config or load_config()).gmail
    path = cfg.credentials_path.strip()
    return bool(path) and Path(path).exists()


def get_gmail_service(config: HubConfig | None = None):
    """Return an authenticated Gmail API service, running the OAuth flow if needed."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    cfg = (config or load_config()).gmail
    creds_path = Path(cfg.credentials_path)
    token_file = _token_path(cfg)
    token_file.parent.mkdir(parents=True, exist_ok=True)

    creds: Credentials | None = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def revoke_gmail_token(config: HubConfig | None = None) -> None:
    """Delete the stored token so the user can re-authenticate."""
    cfg = (config or load_config()).gmail
    token_file = _token_path(cfg)
    if token_file.exists():
        token_file.unlink()
