#!/usr/bin/env bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

mkdir -p "$DIR/logs"

# Check if ADA Gestor Hub is responding on port 5005
IS_RUNNING=$("$DIR/.venv/bin/python" -c "
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:5005/api/health', timeout=1) as resp:
        print(1 if resp.status == 200 else 0)
except Exception:
    print(0)
" 2>/dev/null || echo 0)

if [ "$IS_RUNNING" != "1" ]; then
    # Launch in independent process session with setsid
    ADA_WEB_FRAMEWORK=flask setsid "$DIR/.venv/bin/python" -m ada.interfaces.web.server >> "$DIR/logs/web_server.log" 2>&1 &
    
    # Wait for server to become responsive
    for i in {1..30}; do
        READY=$("$DIR/.venv/bin/python" -c "
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:5005/api/health', timeout=1) as resp:
        print(1 if resp.status == 200 else 0)
except Exception:
    print(0)
" 2>/dev/null || echo 0)
        if [ "$READY" = "1" ]; then
            break
        fi
        sleep 0.5
    done
fi

# Open in default browser or google-chrome
if which xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:5005/" >/dev/null 2>&1 &
elif which google-chrome >/dev/null 2>&1; then
    google-chrome "http://127.0.0.1:5005/" >/dev/null 2>&1 &
fi
