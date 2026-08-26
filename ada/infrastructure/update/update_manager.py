"""Conservative git update workflow for the ADA service.

The manager only fast-forwards a clean checkout and never resets, rebases,
deletes files, or restarts the current process implicitly.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("ada.update")


class UpdateManager:
    def __init__(self, config=None, project_root=None, runner=None, notifier=None):
        self.config = config or {}
        self.root = Path(project_root or Path(__file__).resolve().parents[3]).resolve()
        policy = self.config.get("update") or {}
        self.branch = str(policy.get("branch") or "main")
        state_path = policy.get("state_path") or self.config.get("update_state_path")
        self.state_path = Path(state_path).expanduser() if state_path else self.root / "runtime" / "update.json"
        if not self.state_path.is_absolute():
            self.state_path = (self.root / self.state_path).resolve()
        self.runner = runner or self._run
        self.notifier = notifier
        self._lock = threading.RLock()

    @staticmethod
    def _run(args, cwd):
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
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
                    "status": status,
                    "branch": self.branch,
                    "local_sha": local,
                    "remote_sha": remote,
                    "clean": self._clean(),
                    "checked_at": time.time(),
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
                target_sha = self._git("rev-parse", "HEAD")
                commit_message = self._git("log", "-1", "--format=%s", target_sha)
                restart_required = bool(policy.get("restart_on_update", False))
                payload = {
                    "status": "updated",
                    "branch": self.branch,
                    "commit_sha": target_sha,
                    "commit_message": commit_message,
                    "restart_required": restart_required,
                    "updated_at": time.time(),
                }
                if restart_required:
                    payload["restart_notification"] = self._notify_restart(target_sha, commit_message)
            except Exception as exc:
                payload = {"status": "error", "branch": self.branch, "error": str(exc)}
            self._state(payload)
        return payload

    def _notify_restart(self, commit_sha, commit_message):
        """Notify before the process is restarted; notification failures are non-fatal."""
        if self.notifier is None:
            self.notifier = self._telegram_notifier()
        if self.notifier is None:
            return {"status": "skipped", "reason": "telegram_chat_id_missing"}

        now = datetime.now().astimezone()
        text = (
            "🔄 ADA reiniciando por nuevo commit\n"
            f"Fecha: {now.strftime('%Y-%m-%d')}\n"
            f"Hora: {now.strftime('%H:%M:%S %Z')}\n"
            f"Commit ID: {commit_sha}\n"
            f"Mensaje: {commit_message or '(sin mensaje)'}"
        )
        try:
            message_id = self.notifier(text)
            return {"status": "pending", "message_id": message_id}
        except Exception as exc:
            logger.warning("update_restart_notification_failed error=%s", exc)
            return {"status": "failed", "error": str(exc)}

    def _telegram_notifier(self):
        policy = self.config.get("update") or {}
        telegram = self.config.get("telegram") or {}
        allowed_chat_ids = telegram.get("allowed_chat_ids") or os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
        if isinstance(allowed_chat_ids, str):
            allowed_chat_ids = [item.strip() for item in allowed_chat_ids.split(",") if item.strip()]
        chat_id = (
            policy.get("telegram_chat_id")
            or telegram.get("update_chat_id")
            or os.environ.get("TELEGRAM_UPDATE_CHAT_ID", "")
            or (allowed_chat_ids[0] if allowed_chat_ids else "")
        )
        if not chat_id:
            return None
        try:
            from telegram.bot import TelegramListener

            listener = TelegramListener(self.config)
            if not listener.enabled:
                logger.warning("update_restart_notification_skipped reason=telegram_token_missing")
                return None

            def notify(text):
                return listener.send_message(str(chat_id), text)

            def edit(message_id, text):
                return listener.edit_message_text(str(chat_id), int(message_id), text)

            notify.edit = edit
            return notify
        except Exception as exc:
            logger.warning("update_restart_notification_setup_failed error=%s", exc)
            return None

    def finalize_restart_notification(self, success=True, error=None):
        """Edit the pending restart message once the new process is alive."""
        with self._lock:
            try:
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
                notification = payload.get("restart_notification") or {}
                message_id = notification.get("message_id")
                commit_sha = payload.get("commit_sha", "")
                if notification.get("status") != "pending" or not message_id:
                    return {"status": "skipped", "reason": "no_pending_notification"}
                if self.notifier is None:
                    self.notifier = self._telegram_notifier()
                if self.notifier is None or not hasattr(self.notifier, "edit"):
                    return {"status": "skipped", "reason": "telegram_notifier_unavailable"}
                now = datetime.now().astimezone()
                if success:
                    text = (
                        "✅ ADA reinicio exitoso\n"
                        f"Fecha: {now.strftime('%Y-%m-%d')}\n"
                        f"Hora: {now.strftime('%H:%M:%S %Z')}\n"
                        f"Commit ID: {commit_sha}"
                    )
                else:
                    text = (
                        "❌ ADA reinicio con error\n"
                        f"Fecha: {now.strftime('%Y-%m-%d')}\n"
                        f"Hora: {now.strftime('%H:%M:%S %Z')}\n"
                        f"Commit ID: {commit_sha}\n"
                        f"Error: {error or '(error desconocido)'}"
                    )
                self.notifier.edit(message_id, text)
                payload["restart_notification"] = {
                    **notification,
                    "status": "completed" if success else "failed",
                    "completed_at": time.time(),
                }
                self._state(payload)
                return {"status": payload["restart_notification"]["status"]}
            except Exception as exc:
                logger.warning("update_restart_notification_finalize_failed error=%s", exc)
                return {"status": "failed", "error": str(exc)}

    def run_once(self):
        result = self.check(fetch=False)
        if result.get("status") == "update_available" and (self.config.get("update") or {}).get("auto_pull"):
            return self.apply()
        return result
