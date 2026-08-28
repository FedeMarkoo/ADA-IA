#!/usr/bin/env python3
"""Pull and safely redeploy a changed ADA image with Docker Compose."""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def run(command, env):
    return subprocess.run(command, check=True, capture_output=True, text=True, env=env)


def load_env_file(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def compose(args, env, *parts):
    return run(["docker", "compose", "--env-file", str(args.env_file), "-f", str(args.compose), *parts], env)


def image_id(args, env):
    image = f"{env.get('ADA_IMAGE', 'ghcr.io/fedemarkoo/ada-ia')}:{env.get('ADA_VERSION', 'latest')}"
    result = subprocess.run(
        ["docker", "image", "inspect", "--platform", "linux/amd64", "--format", "{{.Id}}", image],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def running_image_id(args, env):
    result = compose(args, env, "ps", "-q", "ada")
    container_id = result.stdout.strip()
    if not container_id:
        return ""
    inspected = subprocess.run(
        ["docker", "inspect", "--format", "{{.Image}}", container_id],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return inspected.stdout.strip() if inspected.returncode == 0 else ""


def backup_database(data_dir):
    database = data_dir / "db" / "ada.sqlite"
    if not database.exists():
        return None
    backup_dir = data_dir / "backups" / f"deploy-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup = backup_dir / database.name
    import sqlite3

    with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    return backup


def healthcheck(url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(2)
    return False


def rollback(args, env, old_id):
    if not old_id:
        return
    image = f"{env.get('ADA_IMAGE', 'ghcr.io/fedemarkoo/ada-ia')}:{env.get('ADA_VERSION', 'latest')}"
    run(["docker", "tag", old_id, image], env)
    compose(args, env, "up", "-d", "--no-deps", "ada")


def deploy(args):
    env = os.environ.copy()
    file_env = load_env_file(args.env_file)
    for key, value in file_env.items():
        env.setdefault(key, value)
    env.update({"ADA_IMAGE": env.get("ADA_IMAGE", "ghcr.io/fedemarkoo/ada-ia"), "ADA_VERSION": env.get("ADA_VERSION", "latest")})
    old_id = image_id(args, env)
    running_id = running_image_id(args, env)
    backup = backup_database(Path(env.get("ADA_DATA_DIR", "../ada-data")).expanduser().resolve())
    compose(args, env, "pull", "ada")
    new_id = image_id(args, env)
    if old_id and old_id == new_id and running_id == new_id and healthcheck(args.health_url, 5):
        print("No image change and service healthy; deployment skipped.")
        return 0
    try:
        compose(args, env, "up", "-d")
        if not healthcheck(args.health_url, args.health_timeout):
            raise RuntimeError(f"healthcheck failed: {args.health_url}")
    except (subprocess.CalledProcessError, RuntimeError) as error:
        print(f"Deployment failed; rolling back: {error}", file=sys.stderr)
        rollback(args, env, old_id)
        return 1
    print(json.dumps({"deployed": True, "image": new_id, "backup": str(backup) if backup else None}))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose", type=Path, default=Path("compose.yaml"))
    parser.add_argument("--env-file", type=Path, default=Path("deploy/.env"))
    parser.add_argument("--health-url", default="http://127.0.0.1:8081/actuator/health")
    parser.add_argument("--health-timeout", type=int, default=90)
    parser.add_argument("--once", action="store_true", help="Run one check and exit")
    parser.add_argument("--interval", type=int, default=0, help="Repeat every N seconds; 0 runs once")
    args = parser.parse_args()
    args.compose = args.compose.resolve()
    args.env_file = args.env_file.resolve()
    lock_path = args.env_file.parent / ".deploy.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another deployment is already running.", file=sys.stderr)
            return 2
        while True:
            result = deploy(args)
            if args.once or not args.interval:
                return result
            time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
