"""Shared web runtime state, session management and activity tracking for ADA."""

from __future__ import annotations

import logging
import os
import secrets
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app, g, request

from ada.infrastructure.runtime.resources import hardware_profile, recommended_threads

logger = logging.getLogger("ada.web.state")

ADA_VERSION = "0.1.0"
PROCESS_STARTED_AT = datetime.now(timezone.utc).isoformat()

TIMEOUT_PRESETS = {
    "fast": {"router_timeout": 10, "model_timeout": 60, "chat_timeout_seconds": 120, "food_advisor_timeout": 60},
    "balanced": {"router_timeout": 20, "model_timeout": 180, "chat_timeout_seconds": 300, "food_advisor_timeout": 120},
    "patient": {"router_timeout": 30, "model_timeout": 300, "chat_timeout_seconds": 900, "food_advisor_timeout": 180},
}


def find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = find_project_root()
DASHBOARD_DIR = PROJECT_ROOT / "dashboard" if (PROJECT_ROOT / "dashboard").is_dir() else PROJECT_ROOT / "ui"


def ollama_config_payload(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cpu_limit_percent": config.get("cpu_limit_percent", 50),
        "ollama_num_thread": config.get("ollama_num_thread"),
        "ollama_num_ctx": config.get("ollama_num_ctx", 4096),
        "ollama_keep_alive": config.get("ollama_keep_alive", "5m"),
        "ollama_auto_unload": bool(config.get("ollama_auto_unload", False)),
        "ollama_idle_unload_seconds": int(config.get("ollama_idle_unload_seconds", 300)),
        "ollama_temperature": config.get("ollama_temperature", 0.2),
        "timeout_profile": config.get("timeout_profile", "patient"),
        "router_timeout": config.get("router_timeout", 30),
        "model_timeout": config.get("model_timeout", 300),
        "chat_timeout_seconds": config.get("chat_timeout_seconds", 900),
        "food_advisor_timeout": config.get("food_advisor_timeout", 180),
        "timeout_presets": TIMEOUT_PRESETS,
        "recommended_threads": recommended_threads(config),
        "hardware": hardware_profile(),
    }


class PersistentConversation(list):
    """List-compatible history that survives UI and server restarts."""

    def __init__(self, memory, session="main", limit=1000):
        self.memory = memory
        self.session = session
        self.max_messages = max(1, int(limit))
        super().__init__(memory.conversation(session=session, limit=self.max_messages))

    def extend(self, items):
        items = list(items)
        super().extend(items)
        if len(self) > self.max_messages:
            del self[: len(self) - self.max_messages]
        self.memory.append_conversation(items, session=self.session)

    def clear(self):
        super().clear()
        self.memory.clear_conversation(session=self.session)


class WebSessionState:
    def __init__(self, memory, session_id: str, history_limit=1000):
        self.session_id = session_id
        self.conversation = PersistentConversation(memory, session=session_id, limit=history_limit)
        self.pending_action: Optional[Dict[str, Any]] = None
        self.pending_path_action: Optional[Dict[str, Any]] = None
        self.current_path = memory.get_folder_context(session_id) if hasattr(memory, "get_folder_context") else None
        self.last_result: Optional[Dict[str, Any]] = None
        self.lock = threading.RLock()
        self.last_access = time.monotonic()


_task_history: List[Dict[str, Any]] = []
_task_history_lock = threading.RLock()
MAX_TASK_HISTORY = 20


def new_activity_state() -> Dict[str, Any]:
    now = time.time()
    return {
        "status": "idle",
        "phase": "idle",
        "label": "ADA está lista",
        "detail": "Esperando una tarea",
        "component": None,
        "model": None,
        "role": None,
        "channel": None,
        "prompt": "",
        "session_id": None,
        "started_at": None,
        "updated_at": now,
        "recent": [],
        "trace": [],
    }


def activity_descriptor(phase: str, details: Dict[str, Any]) -> tuple[str, str, str, Optional[str]]:
    action = details.get("action")
    descriptors = {
        "received": ("working", "Recibí el pedido", "Preparando la ejecución", "agent"),
        "route_local": ("working", "Eligiendo una ruta local", str(action or "filesystem"), "filesystem"),
        "route_rule": ("working", "Interpretando el pedido", str(action or "regla local"), "router"),
        "folder_resolver_started": (
            "working",
            "Buscando la carpeta",
            str(details.get("context_path") or "Google Drive"),
            "filesystem",
        ),
        "folder_resolver_finished": (
            "working",
            "Carpeta localizada",
            str(details.get("path") or details.get("status") or ""),
            "filesystem",
        ),
        "router_model_started": ("working", "Entendiendo la intención", "Clasificador de pedidos", "router"),
        "router_model_finished": ("working", "Intención comprendida", str(action or "conversación"), "router"),
        "model_started": ("working", "Pensando con el modelo", str(details.get("model") or "modelo local"), "model"),
        "model_finished": ("working", "Respuesta generada", str(details.get("model") or "modelo local"), "model"),
        "capability_started": (
            "working",
            f"Ejecutando {details.get('server') or details.get('capability') or 'herramienta'}",
            f"{details.get('tool') or details.get('capability') or 'acción'}",
            str(details.get("server") or details.get("capability") or "tools"),
        ),
        "capability_finished": (
            "working",
            f"{details.get('tool') or details.get('capability') or 'Herramienta'} finalizada",
            "OK" if details.get("ok", True) else (details.get("error") or "error"),
            str(details.get("server") or details.get("capability") or "tools"),
        ),
        "mcp_started": (
            "working",
            f"Ejecutando MCP {details.get('server') or 'remoto'}",
            str(details.get("tool") or "herramienta MCP"),
            str(details.get("server") or "mcp"),
        ),
        "mcp_finished": (
            "working",
            f"MCP {details.get('tool') or 'herramienta'} finalizado",
            "OK" if details.get("ok", True) else (details.get("error") or "error"),
            str(details.get("server") or "mcp"),
        ),
        "folder_index_updated": (
            "working",
            "Actualizando memoria de carpetas",
            str(details.get("parent") or ""),
            "sqlite-memory",
        ),
        "completed": ("complete", "Tarea completada", str(details.get("detail") or "Resultado entregado"), None),
        "error": (
            "error",
            "La tarea terminó con un error",
            str(details.get("detail") or details.get("error") or "Error"),
            None,
        ),
        "timeout": ("error", "La tarea agotó el tiempo configurado", str(details.get("detail") or "Timeout"), None),
    }
    return descriptors.get(phase, ("working", "ADA está trabajando", phase.replace("_", " "), details.get("component")))


def activity_update(
    runtime: Dict[str, Any], phase: str, details: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None
) -> None:
    details = dict(details or {})
    lock = runtime.setdefault("activity_lock", threading.RLock())
    condition = runtime.setdefault("activity_condition", threading.Condition(lock))
    now = time.time()
    with condition:
        state = runtime.setdefault("activity", new_activity_state())
        status_value, label, detail, component = activity_descriptor(phase, details)

        if phase == "received":
            state["started_at"] = now
            state["prompt"] = str(details.get("message") or "")[:500]
            state["channel"] = details.get("channel") or details.get("source") or "web"
            state["model"] = None
            state["role"] = None
            state["trace"] = []
            state["decision"] = None
            state["execution_steps"] = []

        if phase == "model_started":
            state["model"] = details.get("model")
            state["role"] = details.get("role")

        if phase in {"route_local", "route_rule", "router_model_finished"}:
            state["decision"] = {
                "type": phase,
                "action": details.get("action"),
                "intent": details.get("intent") or label,
                "model": details.get("model") or state.get("model"),
                "at": now,
            }

        if phase.startswith("capability_"):
            state.setdefault("execution_steps", []).append(
                {
                    "phase": phase,
                    "server": details.get("server"),
                    "tool": details.get("tool"),
                    "ok": details.get("ok"),
                    "at": now,
                }
            )

        trace_entry = {
            "phase": phase,
            "label": label,
            "detail": detail[:300],
            "status": status_value,
            "component": component,
            "model": state.get("model"),
            "role": state.get("role"),
            "extra": {
                k: v
                for k, v in details.items()
                if k not in {"message", "detail"} and isinstance(v, (str, int, float, bool, list, dict))
            },
            "at": now,
        }

        trace = list(state.get("trace") or [])
        trace.append(trace_entry)
        state["trace"] = trace[-30:]

        state.update(
            {
                "status": status_value,
                "phase": phase,
                "label": label,
                "detail": detail[:500],
                "component": component,
                "session_id": session_id or state.get("session_id"),
                "updated_at": now,
            }
        )
        recent = list(state.get("recent") or [])
        recent.append({"phase": phase, "label": label, "detail": detail[:180], "status": status_value, "at": now})
        state["recent"] = recent[-12:]

        if phase in {"completed", "error", "timeout"}:
            duration = round(now - float(state.get("started_at") or now), 2)
            task_record = {
                "id": secrets.token_hex(6),
                "prompt": state.get("prompt") or "Tarea interactiva",
                "channel": state.get("channel") or "web",
                "status": status_value,
                "phase": phase,
                "label": label,
                "detail": detail,
                "model": state.get("model"),
                "role": state.get("role"),
                "decision": state.get("decision"),
                "started_at": state.get("started_at") or now,
                "finished_at": now,
                "duration_seconds": duration,
                "trace": list(state.get("trace") or []),
            }
            with _task_history_lock:
                _task_history.insert(0, task_record)
                if len(_task_history) > MAX_TASK_HISTORY:
                    _task_history.pop()
        condition.notify_all()


def activity_snapshot(runtime: Dict[str, Any]) -> Dict[str, Any]:
    lock = runtime.setdefault("activity_lock", threading.RLock())
    with lock:
        snapshot = dict(runtime.setdefault("activity", new_activity_state()))
        snapshot["recent"] = [dict(item) for item in snapshot.get("recent") or []]
        snapshot["trace"] = [dict(item) for item in snapshot.get("trace") or []]
    with _task_history_lock:
        history = [dict(item) for item in _task_history[:10]]
    snapshot["history"] = history
    if snapshot.get("status") == "complete" and time.time() - float(snapshot.get("updated_at") or 0) > 8:
        snapshot.update(
            {
                "status": "idle",
                "phase": "idle",
                "label": "ADA está lista",
                "detail": "Esperando una tarea",
                "component": None,
            }
        )
    return snapshot


def get_runtime() -> Dict[str, Any]:
    """Return the dependencies associated with the current Flask application."""
    runtime = current_app.extensions.get("ada_runtime", {})
    if runtime.get("debug_log") is not None:
        runtime["debug_enabled"] = runtime["debug_log"].enabled()
    return runtime


def get_session_state() -> WebSessionState:
    runtime = get_runtime()
    payload = request.get_json(silent=True) if request.is_json else None
    payload_dict = payload if isinstance(payload, dict) else {}
    session_id = (
        payload_dict.get("session_id")
        or payload_dict.get("conversation_id")
        or request.cookies.get("ada_session")
        or getattr(g, "ada_session_id", None)
    )
    if not session_id:
        session_id = secrets.token_urlsafe(24)
        g.ada_session_id = session_id
    with runtime["session_states_lock"]:
        states = runtime["session_states"]
        now = time.monotonic()
        ttl = max(60, int(runtime.get("session_ttl_seconds", 3600)))
        max_sessions = max(1, int(runtime.get("session_max_count", 256)))
        expired = [key for key, value in states.items() if now - value.last_access > ttl and key != session_id]
        for key in expired:
            states.pop(key, None)
        state = states.get(session_id)
        if state is None:
            state = WebSessionState(
                runtime["agent"].mem,
                session_id,
                history_limit=max(1, int(runtime.get("session_history_limit", 1000))),
            )
            states[session_id] = state
        state.last_access = now
        while len(states) > max_sessions:
            oldest = min(states, key=lambda key: states[key].last_access)
            if oldest == session_id and len(states) > 1:
                oldest = min((key for key in states if key != session_id), key=lambda key: states[key].last_access)
            states.pop(oldest, None)
        return state


# ==============================================================================
# Telegram Process Service Helpers
# ==============================================================================

telegram_proc: Optional[subprocess.Popen] = None
telegram_proc_lock = threading.RLock()
telegram_logs: deque = deque(maxlen=200)


def resolve_telegram_token() -> str:
    from telegram.bot import resolve_telegram_token as resolve_token

    return resolve_token(get_runtime().get("cfg"))


def get_telegram_service_status() -> Dict[str, Any]:
    global telegram_proc
    token = resolve_telegram_token()
    with telegram_proc_lock:
        running = telegram_proc is not None and telegram_proc.poll() is None
        pid = telegram_proc.pid if running else None
    return {
        "configured": bool(token),
        "token_masked": (token[:6] + "..." + token[-4:]) if len(token) > 10 else ("***" if token else None),
        "running": running,
        "pid": pid,
    }


def start_telegram_service() -> Dict[str, Any]:
    global telegram_proc
    token = resolve_telegram_token()
    if not token:
        return {"ok": False, "error": "No hay token de Telegram configurado en vault.db"}
    with telegram_proc_lock:
        if telegram_proc is not None and telegram_proc.poll() is None:
            return {"ok": True, "message": "El servicio ya está en ejecución", "status": get_telegram_service_status()}
        try:
            bot_script = PROJECT_ROOT / "telegram" / "bot.py"
            env = os.environ.copy()
            port = int(os.environ.get("ADA_UI_PORT", "5005"))
            env["ADA_INTERNAL_URL"] = f"http://127.0.0.1:{port}"
            telegram_proc = subprocess.Popen(
                [os.sys.executable, str(bot_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
            )

            def read_logs():
                if telegram_proc and telegram_proc.stdout:
                    for line in telegram_proc.stdout:
                        telegram_logs.append(line.rstrip())

            t = threading.Thread(target=read_logs, daemon=True, name="ada-telegram-logs")
            t.start()
            time.sleep(0.5)
            return {"ok": True, "message": "Servidor de Telegram iniciado", "status": get_telegram_service_status()}
        except Exception as exc:
            return {"ok": False, "error": f"Error al iniciar el bot: {exc}"}


def stop_telegram_service() -> Dict[str, Any]:
    global telegram_proc
    with telegram_proc_lock:
        if telegram_proc is None or telegram_proc.poll() is not None:
            telegram_proc = None
            return {"ok": True, "message": "El servicio no está en ejecución", "status": get_telegram_service_status()}
        try:
            telegram_proc.terminate()
            try:
                telegram_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                telegram_proc.kill()
            telegram_proc = None
            return {"ok": True, "message": "Servidor de Telegram detenido", "status": get_telegram_service_status()}
        except Exception as exc:
            return {"ok": False, "error": f"Error al detener: {exc}"}


def restart_telegram_service() -> Dict[str, Any]:
    stop_telegram_service()
    time.sleep(0.5)
    return start_telegram_service()
