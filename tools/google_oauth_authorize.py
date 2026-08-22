"""Run the local Google OAuth consent flow for ADA without printing tokens."""
from __future__ import annotations

import argparse
import http.server
import json
import secrets
import socketserver
import threading
import urllib.parse
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/gmail.readonly"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    from ada.infrastructure.credentials import SecureVault

    vault = SecureVault()
    client_id = vault.get("google_oauth_client_id")
    client_secret = vault.get("google_oauth_client_secret")
    if not client_id or not client_secret:
        raise SystemExit("Faltan las credenciales OAuth del cliente ADA en la bóveda.")
    state = secrets.token_urlsafe(24)
    redirect = f"http://127.0.0.1:{args.port}/oauth2callback"
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + query
    result = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if params.get("state", [""])[0] != state:
                result["error"] = "OAuth state inválido"
            elif params.get("error"):
                result["error"] = params["error"][0]
            else:
                result["code"] = params.get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ADA ya recibio la autorizacion. Podes cerrar esta pestana.")

        def log_message(self, *_):
            return

    httpd = socketserver.TCPServer(("127.0.0.1", args.port), Callback)
    print(auth_url, flush=True)
    while "code" not in result and "error" not in result:
        httpd.handle_request()
    httpd.server_close()
    if result.get("error"):
        raise SystemExit(result["error"])
    body = urllib.parse.urlencode({
        "code": result["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as response:
        token = json.loads(response.read().decode())
    token["client_id"] = client_id
    token["client_secret"] = client_secret
    token["scopes"] = SCOPES
    vault.set("google_oauth_token", token, meta={"provider": "google", "scopes": SCOPES})
    print("Token OAuth guardado cifrado en la bóveda de ADA.")


if __name__ == "__main__":
    main()
