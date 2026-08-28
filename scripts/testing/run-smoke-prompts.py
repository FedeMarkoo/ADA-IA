#!/usr/bin/env python3
"""Run a small, deterministic smoke suite against ADA's HTTP API."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


DEFAULT_PROMPTS = [
    "Explicá en tres puntos qué es una arquitectura hexagonal.",
    "Compará JPG, PNG y RAW para conservar fotografías.",
    "Tengo arroz, huevos y tomate. Dame dos ideas fáciles para comer ahora.",
]


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
    parser.add_argument("--prompts-file")
    parser.add_argument("prompts", nargs="*")
    args = parser.parse_args()
    prompts = args.prompts
    if args.prompts_file:
        with open(args.prompts_file, encoding="utf-8") as file:
            prompts = [item["prompt"] for item in json.load(file)][:3]
    prompts = prompts or DEFAULT_PROMPTS
    passed = 0
    print(f"Running {len(prompts)} smoke prompts against {args.base_url}")
    for index, prompt in enumerate(prompts, start=1):
        print(f"[{index}/{len(prompts)}] {prompt}")
        try:
            passed += run_prompt(args.base_url, prompt, args.poll_seconds)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as error:
            print(f"  ERROR: {error}", file=sys.stderr)
    print(f"Result: {passed}/{len(prompts)} passed")
    return 0 if passed == len(prompts) else 1


if __name__ == "__main__":
    sys.exit(main())
