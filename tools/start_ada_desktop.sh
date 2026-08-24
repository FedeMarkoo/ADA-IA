#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_SITE="$DIR/.venv/lib/python3.14/site-packages"
SYSTEM_PYTHON="${ADA_SYSTEM_PYTHON:-/usr/bin/python3}"

if [[ ! -x "$SYSTEM_PYTHON" ]]; then
    SYSTEM_PYTHON="$(command -v python3)"
fi

# GTK/WebKitGTK are provided by the system Python, while ADA's Python
# dependencies live in the virtualenv. Put both on the same import path.
export PYTHONPATH="$VENV_SITE:$DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$DIR"
exec "$SYSTEM_PYTHON" -c 'from ada.interfaces.desktop import run; run()'
