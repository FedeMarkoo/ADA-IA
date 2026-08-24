"""Import a Gemini or Groq API key from clipboard into ADA's encrypted vault.

Usage: .venv/bin/python tools/import_provider_token_clipboard.py --provider gemini
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def clipboard_text() -> str:
    for executable, args in (("xclip", ["-selection", "clipboard", "-o"]), ("wl-paste", [])):
        try:
            return subprocess.check_output([executable, *args], text=True, stderr=subprocess.DEVNULL).strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise SystemExit("No encuentro xclip ni wl-paste para leer el portapapeles.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("gemini", "groq"), required=True)
    parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args()
    value = (sys.stdin.read() if args.stdin else clipboard_text()).strip()
    if not value or len(value) > 512 or any(char.isspace() for char in value):
        raise SystemExit("El valor no parece una API key válida.")
    if args.provider == "gemini" and not (value.startswith("AIza") or value.startswith("AQ.")):
        raise SystemExit("La clave de Gemini no tiene un formato reconocido.")
    if args.provider == "groq" and not value.startswith("gsk_"):
        raise SystemExit("La clave de Groq normalmente comienza con gsk_.")
    from ada.infrastructure.credentials import SecureVault
    SecureVault().set(f"{args.provider}_api_key", value, meta={"provider": args.provider, "kind": "api_key"})
    print(f"Clave de {args.provider} guardada cifrada en la bóveda de ADA (contenido no mostrado).")


if __name__ == "__main__":
    main()
