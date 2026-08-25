"""Store Google Programmable Search credentials in ADA's encrypted vault."""
from __future__ import annotations

import argparse
import subprocess
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def clipboard_text() -> str:
    for executable, args in (("xclip", ["-selection", "clipboard", "-o"]), ("wl-paste", [])):
        try:
            return subprocess.check_output([executable, *args], text=True, stderr=subprocess.DEVNULL).strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise SystemExit("No encuentro xclip ni wl-paste para leer el portapapeles.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("api_key", "engine_id"), required=True)
    parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args()
    value = (sys.stdin.read() if args.stdin else clipboard_text()).strip()
    if not value or any(char.isspace() for char in value):
        raise SystemExit("El valor no parece una credencial válida.")
    from ada.infrastructure.credentials import SecureVault
    name = "google_search_api_key" if args.kind == "api_key" else "google_search_engine_id"
    SecureVault().set(name, value, meta={"provider": "google", "kind": args.kind})
    print(f"Credencial Google Search {args.kind} guardada cifrada en la bóveda de ADA.")


if __name__ == "__main__":
    main()
