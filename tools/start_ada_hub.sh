#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

# Check if ADA server is already running on port 5005
if ! curl -s http://127.0.0.1:5005/api/health >/dev/null 2>&1; then
    # Start server in background using the virtualenv
    nohup "$DIR/.venv/bin/ada" serve > "$DIR/logs/web_server.log" 2>&1 &
    # Wait for server to become responsive
    for i in {1..30}; do
        if curl -s http://127.0.0.1:5005/api/health >/dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
fi

# Open in default browser
xdg-open "http://127.0.0.1:5005/" >/dev/null 2>&1 &
