"""Conservative git update workflow for the ADA service.

The manager only fast-forwards a clean checkout and never resets, rebases,
deletes files, or restarts the current process implicitly.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path


class UpdateManager:
    def __init__(self, config=None, project_root=None, runner=None):
        self.config = config or {}
        self.root = Path(project_root or Path(__file__).resolve().parents[3]).resolve()
        policy = self.config.get("update") or {}
        self.branch = str(policy.get("branch") or "main")
        state_path = policy.get("state_path") or self.config.get("update_state_path")
        self.state_path = Path(state_path).expanduser() if state_path else self.root / "runtime" / "update.json"
        if not self.state_path.is_absolute():
            self.state_path = (self.root / self.state_path).resolve()
        self.runner = runner or self._run
        self._lock = threading.RLock()

    @staticmethod
    def _run(args, cwd):
        return subprocess.run(
            ["git", *args], cwd=str(cwd), text=True, capture_output=True,
            check=False, timeout=30,
        )

    def _git(self, *args):
        result = self.runner(list(args), self.root)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "git command failed").strip())
        return result.stdout.strip()

    def _state(self, payload):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def _clean(self):
        dirty = self._git("status", "--porcelain", "--untracked-files=all")
        return not dirty

    def check(self, fetch=False):
        with self._lock:
            try:
                if fetch:
                    self._git("fetch", "origin", self.branch)
                local = self._git("rev-parse", "HEAD")
                remote = self._git("rev-parse", f"refs/remotes/origin/{self.branch}")
                if local == remote:
                    status = "up_to_date"
                else:
                    ancestor = self.runner(["merge-base", "--is-ancestor", local, remote], self.root)
                    status = "update_available" if ancestor.returncode == 0 else "diverged"
                result = {
                    "status": status, "branch": self.branch, "local_sha": local,
                    "remote_sha": remote, "clean": self._clean(), "checked_at": time.time(),
                }
            except Exception as exc:
                result = {"status": "error", "branch": self.branch, "error": str(exc), "checked_at": time.time()}
            self._state(result)
            return result

    def apply(self):
        with self._lock:
            policy = self.config.get("update") or {}
            if not bool(policy.get("auto_pull", False)):
                return {"status": "disabled", "reason": "update.auto_pull is false"}
            if not self._clean():
                return {"status": "blocked", "reason": "worktree_dirty"}
            try:
                self._git("fetch", "origin", self.branch)
                result = self._run(["pull", "--ff-only", "origin", self.branch], self.root)
                if result.returncode != 0:
                    raise RuntimeError((result.stderr or result.stdout).strip())
                payload = {
                    "status": "updated", "branch": self.branch,
                    "restart_required": bool(policy.get("restart_on_update", False)),
                    "updated_at": time.time(),
                }
            except Exception as exc:
                payload = {"status": "error", "branch": self.branch, "error": str(exc)}
            self._state(payload)
            return payload

    def run_once(self):
        result = self.check(fetch=False)
        if result.get("status") == "update_available" and (self.config.get("update") or {}).get("auto_pull"):
            return self.apply()
        return result
