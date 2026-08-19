"""Optional Gmail API adapter; credentials are always supplied outside Git."""

import base64
import json
import os
from email.mime.text import MIMEText
from pathlib import Path


def _service(config, scopes):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Instalá la extra Gmail para habilitar esta integración.") from exc
    credential_name = config.get("gmail_credential_name")
    token_path = None
    if credential_name:
        from ada.infrastructure.credentials import CredentialStore

        token = CredentialStore().get(credential_name)
        if not token:
            raise RuntimeError(f"Falta la credencial cifrada de Gmail: {credential_name}")
        credentials = Credentials.from_authorized_user_info(token, scopes)
    else:
        token_path = Path(os.path.expanduser(config.get("gmail_token_path", "~/.config/ada/gmail-token.json")))
        if not token_path.is_file():
            raise RuntimeError(f"Falta el token OAuth local de Gmail: {token_path}")
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request

        credentials.refresh(Request())
        refreshed_token = json.loads(credentials.to_json())
        if credential_name:
            from ada.infrastructure.credentials import CredentialStore

            CredentialStore().set(credential_name, refreshed_token)
        else:
            token_path = token_path or Path(
                os.path.expanduser(config.get("gmail_token_path", "~/.config/ada/gmail-token.json"))
            )
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(json.dumps(refreshed_token, ensure_ascii=False), encoding="utf-8")
            token_path.chmod(0o600)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def authenticate(config, scopes=None):
    """Run the explicit installed-app OAuth flow and persist the refresh token."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError("Instalá la extra Gmail para iniciar OAuth.") from exc
    scopes = scopes or ["https://www.googleapis.com/auth/gmail.readonly"]
    client_path = Path(os.path.expanduser(config.get("gmail_client_secret_path", "~/.config/ada/google-client.json")))
    if not client_path.is_file():
        raise RuntimeError(f"Falta el client secret OAuth: {client_path}")
    credentials = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes).run_local_server(port=0)
    token = json.loads(credentials.to_json())
    credential_name = config.get("gmail_credential_name")
    if credential_name and os.environ.get("ADA_CREDENTIAL_KEY"):
        from ada.infrastructure.credentials import CredentialStore

        CredentialStore().set(credential_name, token)
    else:
        token_path = Path(os.path.expanduser(config.get("gmail_token_path", "~/.config/ada/gmail-token.json")))
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(json.dumps(token, ensure_ascii=False), encoding="utf-8")
        token_path.chmod(0o600)
    return {"ok": True, "scopes": scopes, "credential_name": credential_name}


def read(config, query="is:unread", limit=10):
    service = _service(config, ["https://www.googleapis.com/auth/gmail.readonly"])
    response = service.users().messages().list(userId="me", q=query, maxResults=max(1, min(int(limit), 50))).execute()
    messages = []
    for item in response.get("messages", []):
        data = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="metadata", metadataHeaders=["Subject", "From", "Date"])
            .execute()
        )
        headers = {header["name"].lower(): header["value"] for header in data.get("payload", {}).get("headers", [])}
        messages.append(
            {
                "id": item["id"],
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
            }
        )
    return {"ok": True, "query": query, "messages": messages}


def send(config, to, subject, body, confirm=False):
    if not confirm:
        return {"error": "confirmation_required", "preview": {"to": to, "subject": subject, "body": body}}
    service = _service(config, ["https://www.googleapis.com/auth/gmail.send"])
    message = MIMEText(str(body), "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"ok": True, "id": result.get("id"), "to": to, "subject": subject}
