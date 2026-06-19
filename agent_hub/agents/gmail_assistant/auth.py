from __future__ import annotations

from pathlib import Path

from agent_hub.core.config import GmailConfig, HubConfig, load_config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
]

_DEFAULT_TOKEN_PATH = Path.home() / ".agent_hub" / "gmail_token.json"


def _token_path(config: GmailConfig) -> Path:
    if config.token_path:
        return Path(config.token_path)
    return _DEFAULT_TOKEN_PATH


def gmail_credentials_configured(config: HubConfig | None = None) -> bool:
    cfg = (config or load_config()).gmail
    path = cfg.credentials_path.strip()
    return bool(path) and Path(path).exists()


def _load_or_refresh_credentials(config: HubConfig | None = None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

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

    return creds


def calendar_scope_granted(config: HubConfig | None = None) -> bool:
    token_file = _token_path((config or load_config()).gmail)
    if not token_file.exists():
        return False
    try:
        import json

        data = json.loads(token_file.read_text(encoding="utf-8"))
        scopes = set(data.get("scopes", []))
        return "https://www.googleapis.com/auth/calendar.readonly" in scopes
    except Exception:
        return False


def get_gmail_service(config: HubConfig | None = None):
    from googleapiclient.discovery import build

    creds = _load_or_refresh_credentials(config)
    return build("gmail", "v1", credentials=creds)


def get_calendar_service(config: HubConfig | None = None):
    from googleapiclient.discovery import build

    creds = _load_or_refresh_credentials(config)
    return build("calendar", "v3", credentials=creds)


def revoke_gmail_token(config: HubConfig | None = None) -> None:
    cfg = (config or load_config()).gmail
    token_file = _token_path(cfg)
    if token_file.exists():
        token_file.unlink()
