from __future__ import annotations

import json
from pathlib import Path

from agent_hub.core.config import GmailConfig, HubConfig, load_config

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
ALL_SCOPES = GMAIL_SCOPES + [CALENDAR_SCOPE]

_DEFAULT_TOKEN_PATH = Path.home() / ".agent_hub" / "gmail_token.json"


def _token_path(config: GmailConfig) -> Path:
    if config.token_path:
        return Path(config.token_path)
    return _DEFAULT_TOKEN_PATH


def _read_token_scopes(token_file: Path) -> list[str]:
    data = json.loads(token_file.read_text(encoding="utf-8"))
    stored = data.get("scopes")
    if stored:
        return list(stored)
    return list(GMAIL_SCOPES)


def gmail_credentials_configured(config: HubConfig | None = None) -> bool:
    cfg = (config or load_config()).gmail
    path = cfg.credentials_path.strip()
    return bool(path) and Path(path).exists()


def _load_or_refresh_credentials(
    config: HubConfig | None = None,
    *,
    oauth_scopes: list[str] | None = None,
):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    cfg = (config or load_config()).gmail
    creds_path = Path(cfg.credentials_path)
    token_file = _token_path(cfg)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    login_scopes = oauth_scopes or ALL_SCOPES

    creds: Credentials | None = None
    if token_file.exists():
        file_scopes = _read_token_scopes(token_file)
        creds = Credentials.from_authorized_user_file(str(token_file), file_scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                message = str(exc).lower()
                if "invalid_scope" in message or "invalid_grant" in message:
                    token_file.unlink(missing_ok=True)
                    creds = None
                else:
                    raise
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), login_scopes)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds


def calendar_scope_granted(config: HubConfig | None = None) -> bool:
    token_file = _token_path((config or load_config()).gmail)
    if not token_file.exists():
        return False
    try:
        return CALENDAR_SCOPE in set(_read_token_scopes(token_file))
    except Exception:
        return False


def get_gmail_service(config: HubConfig | None = None):
    from googleapiclient.discovery import build

    creds = _load_or_refresh_credentials(config, oauth_scopes=ALL_SCOPES)
    return build("gmail", "v1", credentials=creds)


def get_calendar_service(config: HubConfig | None = None):
    from googleapiclient.discovery import build

    if not calendar_scope_granted(config):
        raise RuntimeError(
            "Calendar access not granted. Sign out of Google in the Gmail tab and sign in again."
        )
    creds = _load_or_refresh_credentials(config, oauth_scopes=ALL_SCOPES)
    return build("calendar", "v3", credentials=creds)


def revoke_gmail_token(config: HubConfig | None = None) -> None:
    cfg = (config or load_config()).gmail
    token_file = _token_path(cfg)
    if token_file.exists():
        token_file.unlink()
