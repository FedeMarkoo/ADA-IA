#!/usr/bin/env python3
"""Small read-only Google Calendar MCP backed by ADA's encrypted legacy vault."""

import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet


TOOL = {
    "name": "calendar_upcoming_events",
    "description": "Lista eventos próximos del calendario principal de Google, en formato breve.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "days": {"type": "integer", "minimum": 1, "maximum": 31, "default": 7},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
        },
        "additionalProperties": False,
    },
}


def _setting(name, default):
    return os.environ.get(name, default)


def _vault_value(name):
    vault_path = Path(_setting("ADA_GOOGLE_VAULT_PATH", "/run/secrets/google-vault.db"))
    key_path = Path(_setting("ADA_GOOGLE_VAULT_KEY_PATH", "/run/secrets/google-vault.key"))
    key = key_path.read_text(encoding="utf-8").strip().encode()
    with sqlite3.connect(f"file:{vault_path}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT ciphertext FROM secrets WHERE name = ?", (name,)).fetchone()
    if row is None:
        return None
    return json.loads(Fernet(key).decrypt(row[0]).decode("utf-8"))


def _access_token():
    token = _vault_value("google_oauth_token") or {}
    access_token = token.get("access_token")
    expires_at = float(token.get("refreshed_at", 0)) + float(token.get("expires_in", 0)) - 60
    if access_token and (not token.get("refreshed_at") or time.time() < expires_at):
        return access_token
    refresh_token = token.get("refresh_token")
    client_id = token.get("client_id") or _vault_value("google_oauth_client_id")
    client_secret = token.get("client_secret") or _vault_value("google_oauth_client_secret")
    if not refresh_token or not client_id or not client_secret:
        return access_token
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        refreshed = json.loads(response.read().decode("utf-8"))
    return refreshed.get("access_token") or access_token


def upcoming_events(arguments):
    days = min(max(int(arguments.get("days", 7)), 1), 31)
    max_results = min(max(int(arguments.get("max_results", 10)), 1), 20)
    access_token = _access_token()
    if not access_token:
        return {"status": "error", "message": "Google Calendar no está autenticado."}
    now = datetime.now(timezone.utc)
    query = urllib.parse.urlencode(
        {
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": now.isoformat().replace("+00:00", "Z"),
            "timeMax": (now + timedelta(days=days)).isoformat().replace("+00:00", "Z"),
            "maxResults": max_results,
        }
    )
    request = urllib.request.Request(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events?" + query,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return {"status": "error", "message": f"Google Calendar respondió HTTP {error.code}."}
    events = []
    for item in payload.get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})
        events.append(
            {
                "title": item.get("summary", "Sin título"),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                **({"location": item["location"]} if item.get("location") else {}),
            }
        )
    return {"status": "ok", "calendar": "primary", "days": days, "events": events}
