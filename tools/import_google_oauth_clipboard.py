"""Import Google OAuth JSON from the local clipboard without printing secrets.

Usage:
  python tools/import_google_oauth_clipboard.py --kind client
  python tools/import_google_oauth_clipboard.py --kind client_id --vault
  python tools/import_google_oauth_clipboard.py --kind client_secret --vault
  python tools/import_google_oauth_clipboard.py --kind token
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def clipboard_text() -> str:
    commands = [("xclip", ["-selection", "clipboard", "-o"]), ("wl-paste", [])]
    for executable, args in commands:
        try:
            return subprocess.check_output([executable, *args], text=True, stderr=subprocess.DEVNULL).strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        value = root.clipboard_get()
        root.destroy()
        return value.strip()
    except Exception:
        pass
    raise SystemExit("No encuentro xclip ni wl-paste para leer el portapapeles local.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("client", "token", "client_id", "client_secret"), default="client")
    parser.add_argument("--output")
    parser.add_argument("--vault", action="store_true", help="guardar cifrado en la bóveda de ADA")
    parser.add_argument("--stdin", action="store_true", help="leer el valor desde stdin en vez del portapapeles del sistema")
    args = parser.parse_args()
    raw = sys.stdin.read().strip() if args.stdin else clipboard_text()
    if args.kind in {"client_id", "client_secret"}:
        if not raw or len(raw) > 512:
            raise SystemExit("El portapapeles no contiene un valor OAuth válido.")
        if args.kind == "client_id" and ".apps.googleusercontent.com" not in raw:
            raise SystemExit("El portapapeles no contiene un client_id de Google válido.")
        if args.kind == "client_secret" and not raw.startswith("GOCSPX-"):
            raise SystemExit("El portapapeles no contiene un client_secret de Google válido.")
        payload = raw
    else:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit("El portapapeles no contiene JSON OAuth válido.") from exc
    if args.kind == "client":
        if not (payload.get("installed") or payload.get("web") or payload.get("client_id")):
            raise SystemExit("El JSON no parece ser un cliente OAuth de Google.")
        default = Path.home() / ".config" / "ada" / "google-client.json"
    elif args.kind == "token":
        if not payload.get("refresh_token"):
            raise SystemExit("El JSON no contiene refresh_token de OAuth.")
        default = Path.home() / ".config" / "ada" / "google-token.json"
    else:
        default = Path.home() / ".config" / "ada" / f"google-{args.kind}.txt"
    if args.vault:
        from ada.infrastructure.credentials import SecureVault

        name = {
            "client": "google_oauth_client",
            "token": "google_oauth_token",
            "client_id": "google_oauth_client_id",
            "client_secret": "google_oauth_client_secret",
        }[args.kind]
        SecureVault().set(name, payload, meta={"provider": "google", "kind": args.kind})
        print(f"OAuth {args.kind} guardado cifrado en la bóveda de ADA (contenido sensible no mostrado).")
    else:
        target = Path(os.path.expanduser(args.output)) if args.output else default
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        target.chmod(0o600)
        print(f"OAuth {args.kind} guardado en {target} (contenido sensible no mostrado).")


if __name__ == "__main__":
    main()
