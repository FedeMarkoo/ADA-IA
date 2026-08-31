#!/usr/bin/env python3
"""Seed and execute a smoke suite whose prompts live in external SQLite."""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


CREATE_PROMPTS_TABLE = """
CREATE TABLE IF NOT EXISTS smoke_prompts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def database_path(argument):
    if argument:
        return Path(argument)
    configured = os.environ.get("ADA_DATA_DIR")
    if configured:
        data_dir = Path(configured).expanduser()
        if not data_dir.is_absolute():
            data_dir = Path(__file__).resolve().parents[2] / data_dir
    else:
        data_dir = Path(__file__).resolve().parents[2] / "../ada-data"
    return data_dir.resolve() / "db" / "ada.sqlite"


def seed_prompts(database, seed_file):
    database.parent.mkdir(parents=True, exist_ok=True)
    with seed_file.open(encoding="utf-8") as file:
        prompts = json.load(file)
    with sqlite3.connect(database) as connection:
        connection.execute(CREATE_PROMPTS_TABLE)
        connection.executemany(
            """
            INSERT INTO smoke_prompts(id, name, prompt, enabled)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                prompt=excluded.prompt, enabled=excluded.enabled
            """,
            [(item["id"], item["name"], item["prompt"]) for item in prompts],
        )
    return len(prompts)


def load_prompts(database, limit):
    with sqlite3.connect(database) as connection:
        connection.execute(CREATE_PROMPTS_TABLE)
        rows = connection.execute(
            "SELECT id, name, prompt FROM smoke_prompts WHERE enabled = 1 ORDER BY rowid LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"id": row[0], "name": row[1], "prompt": row[2]} for row in rows]


def request(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def run_prompt(base_url, prompt, poll_seconds):
    accepted = request(f"{base_url}/api/v1/chat", {"message": prompt})
    message_id = accepted["messageId"]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        status = request(f"{base_url}/api/v1/chat/{message_id}/status")
        state_name = status.get("state", "unknown").upper()
        print(f"  {message_id} -> {state_name}", flush=True)
        if state_name in {"COMPLETED", "FAILED"}:
            if state_name == "FAILED":
                return False
            result = request(f"{base_url}/api/v1/chat/{message_id}")
            print(
                f"  response model={result.get('model')} "
                f"input_tokens={result.get('inputTokens')} "
                f"output_tokens={result.get('outputTokens')} "
                f"token_usage={result.get('tokenUsage')}",
                flush=True,
            )
            print(f"  response: {result.get('content')}", flush=True)
            return True
        time.sleep(poll_seconds)
    print(f"  {message_id} -> TIMEOUT", flush=True)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--database", help="External SQLite file containing smoke_prompts")
    parser.add_argument("--seed-file", type=Path, help="JSON fixture used to upsert prompts into SQLite")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be greater than zero")
    database = database_path(args.database)
    database.parent.mkdir(parents=True, exist_ok=True)
    if args.seed_file:
        print(f"Seeded {seed_prompts(database, args.seed_file)} prompts in {database}")
    prompts = load_prompts(database, args.limit)
    if not prompts:
        print(f"No enabled prompts found in {database}. Use --seed-file first.", file=sys.stderr)
        return 2
    passed = 0
    print(f"Running {len(prompts)} SQLite smoke prompts against {args.base_url}")
    for index, item in enumerate(prompts, start=1):
        print(f"[{index}/{len(prompts)}] {item['id']} - {item['name']}")
        try:
            passed += run_prompt(args.base_url, item["prompt"], args.poll_seconds)
        except (OSError, urllib.error.URLError, KeyError, json.JSONDecodeError) as error:
            print(f"  ERROR: {error}", file=sys.stderr)
    print(f"Result: {passed}/{len(prompts)} passed")
    return 0 if passed == len(prompts) else 1


if __name__ == "__main__":
    sys.exit(main())
