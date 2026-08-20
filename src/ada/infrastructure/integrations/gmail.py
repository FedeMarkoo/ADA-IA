"""Optional Gmail API adapter; credentials are always supplied outside Git."""

import base64
import json
import os
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlparse

from ada.infrastructure.integrations.mcp import MCPClient


READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _load_credentials(config, scopes):
    try:
        from google.oauth2.credentials import Credentials
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
    return credentials, token_path


def _save_credentials(config, credentials, token_path):
    refreshed_token = json.loads(credentials.to_json())
    credential_name = config.get("gmail_credential_name")
    if credential_name:
        from ada.infrastructure.credentials import CredentialStore

        CredentialStore().set(credential_name, refreshed_token)
        return
    token_path = token_path or Path(
        os.path.expanduser(config.get("gmail_token_path", "~/.config/ada/gmail-token.json"))
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(refreshed_token, ensure_ascii=False), encoding="utf-8")
    token_path.chmod(0o600)


def _refresh_request():
    try:
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError("Instalá la extra Gmail para renovar credenciales OAuth.") from exc
    return Request()


def _credentials(config, scopes):
    credentials, token_path = _load_credentials(config, scopes)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(_refresh_request())
        _save_credentials(config, credentials, token_path)
    if credentials.expired:
        raise RuntimeError("La credencial OAuth de Gmail expiró y no tiene refresh token.")
    if not credentials.token:
        raise RuntimeError("La credencial OAuth de Gmail no contiene un access token.")
    return credentials


def _service(config, scopes):
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Instalá la extra Gmail para habilitar esta integración.") from exc
    credentials = _credentials(config, scopes)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _gmail_mcp_server(config):
    servers = config.get("mcp_servers") or config.get("mcpServers") or {}
    name = config.get("gmail_mcp_server", "gmail")
    server = servers.get(name) if isinstance(servers, dict) else None
    if not isinstance(server, dict):
        raise RuntimeError(f"Configurá el servidor MCP de Gmail bajo mcp_servers.{name}.")
    url = server.get("url") or server.get("serverUrl")
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("El servidor MCP de Gmail debe usar una URL HTTPS válida.")
    if parsed.username or parsed.password:
        raise RuntimeError("La URL MCP de Gmail no puede contener credenciales.")
    allowed_hosts = config.get("gmail_mcp_allowed_hosts") or ["gmailmcp.googleapis.com"]
    if not isinstance(allowed_hosts, (list, tuple, set)):
        raise RuntimeError("gmail_mcp_allowed_hosts debe ser una lista.")
    if parsed.hostname not in {str(host).lower() for host in allowed_hosts}:
        raise RuntimeError(f"Host MCP de Gmail no permitido: {parsed.hostname}")
    if server.get("type") not in (None, "http"):
        raise RuntimeError("El servidor MCP de Gmail debe usar transporte HTTP.")
    return server


def _gmail_mcp_client(config, scopes):
    server = dict(_gmail_mcp_server(config))
    credentials = _credentials(config, scopes)
    raw_headers = server.get("headers") or {}
    if not isinstance(raw_headers, dict):
        raise RuntimeError("Los headers del servidor MCP de Gmail deben ser un objeto.")
    headers = {str(key): str(value) for key, value in raw_headers.items() if str(key).lower() != "authorization"}
    headers["Authorization"] = f"Bearer {credentials.token}"
    server["headers"] = headers
    return MCPClient(server, timeout=float(config.get("gmail_mcp_timeout", 60)))


def _mcp_call(config, scopes, tool, arguments):
    response = _gmail_mcp_client(config, scopes).call(tool=tool, arguments=arguments)
    return {
        "ok": True,
        "backend": "mcp",
        "tool": tool,
        "result": response.get("result", response) if isinstance(response, dict) else response,
    }


def authenticate(config, scopes=None):
    """Run the explicit installed-app OAuth flow and persist the refresh token."""
    scopes = scopes or config.get("gmail_scopes") or [READ_SCOPE, COMPOSE_SCOPE, SEND_SCOPE]
    credential_name = config.get("gmail_credential_name")
    if credential_name and not os.environ.get("ADA_CREDENTIAL_KEY"):
        raise RuntimeError("Definí ADA_CREDENTIAL_KEY para guardar la credencial cifrada de Gmail.")
    client_path = Path(os.path.expanduser(config.get("gmail_client_secret_path", "~/.config/ada/google-client.json")))
    if not client_path.is_file():
        raise RuntimeError(f"Falta el client secret OAuth: {client_path}")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError("Instalá la extra Gmail para iniciar OAuth.") from exc
    credentials = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes).run_local_server(port=0)
    token = json.loads(credentials.to_json())
    if credential_name:
        from ada.infrastructure.credentials import CredentialStore

        CredentialStore().set(credential_name, token)
    else:
        token_path = Path(os.path.expanduser(config.get("gmail_token_path", "~/.config/ada/gmail-token.json")))
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(json.dumps(token, ensure_ascii=False), encoding="utf-8")
        token_path.chmod(0o600)
    return {"ok": True, "scopes": scopes, "credential_name": credential_name}


def read(config, query="is:unread", limit=10):
    limit = max(1, min(int(limit), 50))
    if config.get("gmail_backend", "api") == "mcp":
        return _mcp_call(
            config,
            [READ_SCOPE],
            "search_threads",
            {"query": query, "pageSize": limit, "view": "THREAD_VIEW_MINIMAL"},
        )
    service = _service(config, [READ_SCOPE])
    response = service.users().messages().list(userId="me", q=query, maxResults=limit).execute()
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
    service = _service(config, [SEND_SCOPE])
    message = MIMEText(str(body), "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"ok": True, "id": result.get("id"), "to": to, "subject": subject}


def draft(config, to, subject, body, confirm=False):
    """Create a Gmail draft; sending remains the confirmation boundary."""
    preview = {"to": str(to), "subject": str(subject), "body": str(body)}
    if config.get("gmail_backend", "api") == "mcp":
        recipients = [str(to)] if to else []
        result = _mcp_call(
            config,
            [COMPOSE_SCOPE],
            "create_draft",
            {"to": recipients, "subject": str(subject), "body": str(body)},
        )
        result["preview"] = preview
        return result
    service = _service(config, [COMPOSE_SCOPE])
    message = MIMEText(str(body), "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    result = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"ok": True, "id": result.get("id"), "message_id": result.get("message", {}).get("id"), "preview": preview}
