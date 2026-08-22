"""Persistent lifecycle management for ADA's external event sources.

The dashboard owns desired state and lifecycle controls, while long-running
connectors live outside the web process.  This lets Telegram (and future event
sources) survive dashboard reloads and server restarts.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

logger = logging.getLogger("ada.triggers")


TRIGGER_CATALOG = (
    {
        "id": "telegram",
        "name": "Telegram",
        "kind": "channel",
        "description": "Mensajes, comandos y fotos recibidos por el bot.",
        "implementation": "managed",
    },
    {
        "id": "removable-device",
        "name": "Dispositivo / SD",
        "kind": "device",
        "description": "Conexión de tarjetas SD, cámaras, teléfonos o discos externos.",
        "implementation": "ready",
    },
    {
        "id": "calendar",
        "name": "Calendarios",
        "kind": "schedule",
        "description": "Eventos próximos, cambios y recordatorios de calendarios conectados.",
        "implementation": "ready",
    },
    {
        "id": "cron",
        "name": "Tareas programadas",
        "kind": "schedule",
        "description": "Reglas horarias y tareas periódicas administradas por ADA.",
        "implementation": "ready",
    },
    {
        "id": "webhook",
        "name": "Webhooks",
        "kind": "event",
        "description": "Eventos HTTP autenticados enviados por servicios externos.",
        "implementation": "ready",
    },
)


class TriggerManager:
    """Manage desired state and detached processes for ADA trigger sources."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]],
        project_root: Path | str,
        config_path: Optional[Path | str] = None,
        state_dir: Optional[Path | str] = None,
        internal_url: str = "http://127.0.0.1:5005",
        telegram_command: Optional[list[str]] = None,
        discover_existing: bool = True,
    ):
        self.config = config if isinstance(config, dict) else {}
        self.project_root = Path(project_root).resolve()
        self.config_path = Path(config_path).resolve() if config_path else None
        default_state = Path.home() / "Desktop" / "ADA_Data" / "runtime" / "triggers"
        self.state_dir = Path(state_dir or self.config.get("trigger_state_dir") or default_state).expanduser()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.internal_url = internal_url.rstrip("/")
        self.telegram_command = telegram_command or [sys.executable, str(self.project_root / "telegram" / "bot.py")]
        self.discover_existing = bool(discover_existing)
        self._lock = threading.RLock()
        self._watchdog_stop = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._last_start_attempt = 0.0

    @property
    def telegram_state_path(self) -> Path:
        return self.state_dir / "telegram.json"

    @property
    def telegram_log_path(self) -> Path:
        return self.state_dir / "telegram.log"

    @property
    def telegram_health_path(self) -> Path:
        return self.state_dir / "telegram-health.json"

    def _read_state(self) -> Dict[str, Any]:
        try:
            return json.loads(self.telegram_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def _write_state(self, data: Dict[str, Any]) -> None:
        temporary = self.telegram_state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.telegram_state_path)

    def _telegram_process(self, pid: Any) -> Optional[psutil.Process]:
        try:
            process = psutil.Process(int(pid))
            if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                return None
            command = " ".join(process.cmdline())
            expected = str(self.project_root / "telegram" / "bot.py")
            if expected not in command and "telegram.bot" not in command:
                return None
            return process
        except (psutil.Error, TypeError, ValueError):
            return None

    def _discover_telegram_process(self) -> Optional[psutil.Process]:
        if not self.discover_existing:
            return None
        expected = str(self.project_root / "telegram" / "bot.py")
        for process in psutil.process_iter(["pid", "cmdline"]):
            try:
                command = " ".join(process.info.get("cmdline") or [])
                if expected in command or ("telegram.bot" in command and str(self.project_root) in command):
                    return process
            except (psutil.Error, TypeError):
                continue
        return None

    def _resolve_token(self) -> str:
        from telegram.bot import resolve_telegram_token

        return resolve_telegram_token(self.config)

    def _event_token_is_configured(self) -> bool:
        if os.environ.get("ADA_EVENT_TOKEN") or self.config.get("event_token"):
            return True
        try:
            from ada.infrastructure.credentials import SecureVault

            return bool(SecureVault().get("event_token") or SecureVault().get("ada_event_token"))
        except Exception:
            return False

    def _log_tail(self, lines: int = 12) -> list[str]:
        try:
            values = self.telegram_log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        except OSError:
            return []
        try:
            token = self._resolve_token()
        except Exception:
            token = ""
        if token:
            values = [line.replace(token, "***") for line in values]
        return values

    def _health(self) -> Dict[str, Any]:
        try:
            return json.loads(self.telegram_health_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def _persist_enabled(self, enabled: bool) -> None:
        telegram = self.config.setdefault("telegram", {})
        if not isinstance(telegram, dict):
            telegram = {}
            self.config["telegram"] = telegram
        telegram["enabled"] = bool(enabled)
        if not self.config_path:
            return
        saved = {}
        try:
            if self.config_path.is_file():
                saved = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                saved = {}
            if not isinstance(saved.get("telegram"), dict):
                saved["telegram"] = {}
            saved["telegram"]["enabled"] = bool(enabled)
            temporary = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
            temporary.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self.config_path)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("trigger_config_persist_failed trigger=telegram error=%s", exc)

    def telegram_status(self) -> Dict[str, Any]:
        with self._lock:
            state = self._read_state()
            process = self._telegram_process(state.get("pid"))
            if process is None:
                process = self._discover_telegram_process()
                if process is not None:
                    state = {
                        "pid": process.pid,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "adopted": True,
                    }
                    self._write_state(state)
            token = self._resolve_token()
            desired = bool((self.config.get("telegram") or {}).get("enabled", False))
            running = process is not None
            health = self._health() if running else {}
            exit_reason = None
            if not running and state.get("pid"):
                exit_reason = "El proceso terminó; ADA volverá a iniciarlo mientras esté habilitado."
            reported_status = "running" if running else ("recovering" if desired and token else "stopped")
            if running and health.get("status") == "starting":
                reported_status = "starting"
            if running and health.get("status") == "degraded":
                reported_status = "degraded"
            raw_error = health.get("last_error") or exit_reason
            error_code = None
            if raw_error and "Telegram API 409" in raw_error:
                error_code = "listener_conflict"
                visible_error = (
                    "Otro equipo o servicio está consultando este mismo bot. Telegram admite un solo listener "
                    "por token; detené la otra instancia o renová el token desde @BotFather."
                )
            else:
                visible_error = raw_error
            return {
                "id": "telegram",
                "ok": running and bool(token) and reported_status != "degraded",
                "configured": bool(token),
                "token_set": bool(token),
                "running": running,
                "desired_state": "running" if desired else "stopped",
                "status": reported_status,
                "pid": process.pid if process else None,
                "started_at": state.get("started_at"),
                "survives_dashboard_restart": True,
                "managed_externally": True,
                "log_path": str(self.telegram_log_path),
                "health_updated_at": health.get("updated_at"),
                "error_code": error_code,
                "last_error": visible_error,
                "recent_log": self._log_tail(),
            }

    def start(self, trigger_id: str, persist: bool = True) -> Dict[str, Any]:
        if trigger_id != "telegram":
            return {"ok": False, "error": "Este disparador todavía no tiene un adaptador ejecutable."}
        with self._lock:
            if persist:
                self._persist_enabled(True)
            current = self.telegram_status()
            if current["running"]:
                return {"ok": True, "message": "Telegram ya está en ejecución", **current}
            if not current["configured"]:
                return {"ok": False, "error": "Falta configurar el token de Telegram."}
            self._last_start_attempt = time.monotonic()
            self.telegram_log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = self.telegram_log_path.open("ab", buffering=0)
            environment = os.environ.copy()
            environment["ADA_INTERNAL_URL"] = self.internal_url
            environment["ADA_TRIGGER_HEALTH_PATH"] = str(self.telegram_health_path)
            environment["PYTHONUNBUFFERED"] = "1"
            popen_options: Dict[str, Any] = {"start_new_session": True} if os.name != "nt" else {
                "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            }
            try:
                process = subprocess.Popen(
                    self.telegram_command,
                    cwd=str(self.project_root),
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                    **popen_options,
                )
            finally:
                log_handle.close()
            state = {
                "pid": process.pid,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "command": self.telegram_command,
                "log_path": str(self.telegram_log_path),
            }
            self._write_state(state)
            time.sleep(0.15)
            if process.poll() is not None:
                return {"ok": False, "error": "Telegram terminó al iniciar.", "recent_log": self._log_tail()}
            logger.info("trigger_started trigger=telegram pid=%s", process.pid)
            return {"ok": True, "message": "Telegram iniciado como servicio independiente", **self.telegram_status()}

    def stop(self, trigger_id: str, persist: bool = True, timeout: float = 8.0) -> Dict[str, Any]:
        if trigger_id != "telegram":
            return {"ok": False, "error": "Este disparador todavía no tiene un adaptador ejecutable."}
        with self._lock:
            if persist:
                self._persist_enabled(False)
            state = self._read_state()
            process = self._telegram_process(state.get("pid")) or self._discover_telegram_process()
            if process is None:
                self.telegram_state_path.unlink(missing_ok=True)
                self.telegram_health_path.unlink(missing_ok=True)
                return {**self.telegram_status(), "ok": True, "message": "Telegram ya estaba detenido"}
            process.terminate()
            try:
                process.wait(timeout=max(0.5, timeout))
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            self.telegram_state_path.unlink(missing_ok=True)
            self.telegram_health_path.unlink(missing_ok=True)
            logger.info("trigger_stopped trigger=telegram pid=%s", process.pid)
            return {**self.telegram_status(), "ok": True, "message": "Telegram detenido"}

    def restart(self, trigger_id: str) -> Dict[str, Any]:
        stopped = self.stop(trigger_id, persist=False)
        if not stopped.get("ok"):
            return stopped
        return self.start(trigger_id, persist=True)

    def reconcile(self) -> Dict[str, Any]:
        status = self.telegram_status()
        if status["desired_state"] == "running" and status["configured"] and not status["running"]:
            if time.monotonic() - self._last_start_attempt >= 10:
                return self.start("telegram", persist=False)
        return status

    def start_watchdog(self, interval: float = 5.0) -> Optional[threading.Thread]:
        with self._lock:
            if self._watchdog_thread and self._watchdog_thread.is_alive():
                return self._watchdog_thread
            self._watchdog_stop.clear()

            def watch() -> None:
                while not self._watchdog_stop.wait(max(2.0, float(interval))):
                    try:
                        self.reconcile()
                    except Exception:
                        logger.exception("trigger_watchdog_failed")

            self._watchdog_thread = threading.Thread(target=watch, name="ada-trigger-watchdog", daemon=True)
            self._watchdog_thread.start()
            return self._watchdog_thread

    def list_triggers(self, reconcile: bool = False) -> list[Dict[str, Any]]:
        telegram = self.reconcile() if reconcile else self.telegram_status()
        trigger_config = self.config.get("triggers") if isinstance(self.config.get("triggers"), dict) else {}
        results = []
        for definition in TRIGGER_CATALOG:
            item = dict(definition)
            if item["id"] == "telegram":
                item.update(telegram)
                item["controllable"] = True
                item["summary"] = "Proceso independiente administrado por ADA"
            else:
                configured = trigger_config.get(item["id"], {}) if isinstance(trigger_config, dict) else {}
                enabled = bool(configured.get("enabled", False)) if isinstance(configured, dict) else False
                item.update({
                    "configured": bool(configured),
                    "running": False,
                    "desired_state": "running" if enabled else "stopped",
                    "status": "ready" if not enabled else "needs_adapter",
                    "controllable": False,
                    "summary": "Contrato de eventos preparado; falta conectar el adaptador",
                })
                if item["id"] == "webhook":
                    item["endpoint"] = "/api/events"
                    item["configured"] = self._event_token_is_configured()
                    item["status"] = "ready" if item["configured"] else "needs_config"
                    item["summary"] = "Endpoint disponible" if item["configured"] else "Falta configurar ADA_EVENT_TOKEN"
            results.append(item)
        return results

    def summary(self, reconcile: bool = False) -> Dict[str, Any]:
        triggers = self.list_triggers(reconcile=reconcile)
        return {
            "ok": True,
            "triggers": triggers,
            "counts": {
                "total": len(triggers),
                "running": sum(1 for item in triggers if item.get("running")),
                "ready": sum(1 for item in triggers if item.get("status") in {"ready", "running"}),
                "needs_attention": sum(1 for item in triggers if item.get("status") in {"recovering", "degraded", "needs_config", "needs_adapter"}),
            },
        }
