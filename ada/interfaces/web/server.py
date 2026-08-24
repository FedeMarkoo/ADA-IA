from flask import Flask, current_app, request, jsonify, send_from_directory, Response, stream_with_context, g
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from pathlib import Path
from typing import Any, Dict, Optional

from ada.application.agent import Agent
from ada.application.services.web_chat import WebChatService
from ada.config import load_config, validate_config
from ada.infrastructure.runtime.resources import hardware_profile, recommended_threads
from ada.infrastructure.runtime.triggers import TriggerManager
from ada.interfaces.i18n import tr
from ada.ollama.client import OllamaClient
from ada.models.catalog import ModelCatalog
from ada.models.benchmark import ModelBenchmark
from ada.mcps.manager import MCPManager
from ada.interfaces.web.doctor import HealthDoctor
from ada.infrastructure.runtime.duplicates import detect_duplicates
from ada.infrastructure.observability_timeseries import TimeSeriesStore, metrics_scraper_status
from ada.infrastructure.persistence.debug_log import DebugLog
from ada.application.services.memory_refiner import MemoryRefiner
from ada.application.services.healthcheck import HealthcheckStore, evaluate as evaluate_healthcheck, functional_category, llm_judge, requires_mcp
import re
import secrets
import threading
from datetime import datetime, timezone

ADA_VERSION = "0.1.0"
PROCESS_STARTED_AT = datetime.now(timezone.utc).isoformat()

TIMEOUT_PRESETS = {
    "fast": {"router_timeout": 10, "model_timeout": 60, "chat_timeout_seconds": 120, "food_advisor_timeout": 60},
    "balanced": {"router_timeout": 20, "model_timeout": 180, "chat_timeout_seconds": 300, "food_advisor_timeout": 120},
    "patient": {"router_timeout": 30, "model_timeout": 300, "chat_timeout_seconds": 900, "food_advisor_timeout": 180},
}


def _ollama_config_payload(config):
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

def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[3]

PROJECT_ROOT = _find_project_root()
DASHBOARD_DIR = PROJECT_ROOT / "dashboard" if (PROJECT_ROOT / "dashboard").is_dir() else PROJECT_ROOT / "ui"
app = Flask(__name__, static_folder=str(DASHBOARD_DIR), static_url_path="/static")


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    current_app.logger.exception("Unhandled ADA request error")
    correlation_id = secrets.token_hex(8)
    app.logger.error("request_failed correlation_id=%s", correlation_id)
    return (
        jsonify(
            {
                "error": "internal_error",
                "message": "Error interno. Reintentá más tarde.",
                "correlation_id": correlation_id,
            }
        ),
        500,
    )


def _csrf_token():
    return request.cookies.get("ada_csrf") or secrets.token_urlsafe(32)


@app.before_request
def protect_mutating_requests():
    if request.method not in {"POST", "DELETE", "PUT", "PATCH"}:
        return None
    if request.path == "/api/events":
        if (request.content_type or "").split(";", 1)[0].lower() != "application/json":
            return jsonify({"error": "content_type_must_be_json"}), 415
        expected = os.environ.get("ADA_EVENT_TOKEN") or _runtime()["cfg"].get("event_token")
        if not expected:
            try:
                from ada.infrastructure.credentials import SecureVault

                expected = SecureVault().get("event_token") or SecureVault().get("ada_event_token")
            except Exception:
                expected = None
        supplied = request.headers.get("X-ADA-Event-Token", "")
        if not expected or not supplied or not secrets.compare_digest(str(expected), supplied):
            return jsonify({"error": "event_token_required"}), 403
        return None
    if request.host.split(":", 1)[0].lower() not in {"127.0.0.1", "localhost"}:
        return jsonify({"error": "invalid_host"}), 403
    origin = request.headers.get("Origin")
    if origin and not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin, re.I):
        return jsonify({"error": "invalid_origin"}), 403
    if request.path.startswith("/api/"):
        if request.method in ["POST", "PUT", "PATCH"]:
            if (request.content_type or "").split(";", 1)[0].lower() != "application/json":
                return jsonify({"error": "content_type_must_be_json"}), 415
        cookie_csrf = request.cookies.get("ada_csrf", "")
        # Enforce CSRF only when request originates from a browser session with ada_csrf cookie
        if cookie_csrf:
            token = request.headers.get("X-ADA-Token", "")
            if not token or not secrets.compare_digest(token, cookie_csrf):
                return jsonify({"error": "csrf_token_required"}), 403
    return None


@app.after_request
def hide_provider_metadata(response):
    """Keep engine/provider details out of public conversation responses."""
    if request.path == "/api/chat" and response.is_json:
        payload = response.get_json(silent=True)
        if isinstance(payload, dict) and "model" in payload:
            payload.pop("model", None)
            response.set_data(json.dumps(payload, ensure_ascii=False))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


cfg_path = PROJECT_ROOT / "ada" / "config.json" if (PROJECT_ROOT / "ada" / "config.json").exists() else PROJECT_ROOT / "config.json"
cfg = load_config(cfg_path, PROJECT_ROOT)

mcp_manager = MCPManager(cfg)
agent = Agent(cfg, mcp_manager=mcp_manager)
web_chat = WebChatService(agent, cfg, mcp_manager=mcp_manager)
ollama_client = OllamaClient(cfg.get("ollama_url", "http://127.0.0.1:11434"))
model_catalog = ModelCatalog(cfg)
model_benchmark = ModelBenchmark(cfg.get("ollama_url", "http://127.0.0.1:11434"))
trigger_manager = TriggerManager(
    cfg,
    PROJECT_ROOT,
    config_path=cfg_path,
    internal_url=f"http://127.0.0.1:{int(os.environ.get('ADA_UI_PORT', '5005'))}",
)
memory_refiner = MemoryRefiner(agent.mem, agent=agent, config=cfg)
if memory_refiner.enabled:
    memory_refiner.start()



class PersistentConversation(list):
    """List-compatible history that survives UI and server restarts."""

    def __init__(self, memory, session="main"):
        self.memory = memory
        self.session = session
        super().__init__(memory.conversation(session=session, limit=1000))

    def extend(self, items):
        items = list(items)
        super().extend(items)
        self.memory.append_conversation(items, session=self.session)

    def clear(self):
        super().clear()
        self.memory.clear_conversation(session=self.session)


class WebSessionState:
    def __init__(self, memory, session_id):
        self.session_id = session_id
        self.conversation = PersistentConversation(memory, session=session_id)
        self.pending_action: Optional[Dict[str, Any]] = None
        self.pending_path_action: Optional[Dict[str, Any]] = None
        self.current_path = memory.get_folder_context(session_id) if hasattr(memory, "get_folder_context") else None
        self.last_result: Optional[Dict[str, Any]] = None
        self.lock = threading.RLock()


session_states: Dict[str, WebSessionState] = {}
session_states_lock = threading.RLock()


def _chat_workers(config):
    configured = config.get("chat_workers")
    if configured is not None:
        return max(1, min(32, int(configured)))
    return max(2, min(8, os.cpu_count() or 2))


_task_history = []
_task_history_lock = threading.RLock()
MAX_TASK_HISTORY = 20


def _new_activity_state():
    now = time.time()
    return {
        "status": "idle", "phase": "idle", "label": "ADA está lista",
        "detail": "Esperando una tarea", "component": None, "model": None,
        "role": None, "channel": None, "prompt": "", "session_id": None,
        "started_at": None, "updated_at": now, "recent": [],
        "trace": [],
    }


def _activity_descriptor(phase, details):
    action = details.get("action")
    capability = details.get("capability")
    descriptors = {
        "received": ("working", "Recibí el pedido", "Preparando la ejecución", "agent"),
        "route_local": ("working", "Eligiendo una ruta local", str(action or "filesystem"), "filesystem"),
        "route_rule": ("working", "Interpretando el pedido", str(action or "regla local"), "router"),
        "folder_resolver_started": ("working", "Buscando la carpeta", str(details.get("context_path") or "Google Drive"), "filesystem"),
        "folder_resolver_finished": ("working", "Carpeta localizada", str(details.get("path") or details.get("status") or ""), "filesystem"),
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
        "folder_index_updated": ("working", "Actualizando memoria de carpetas", str(details.get("parent") or ""), "sqlite-memory"),
        "completed": ("complete", "Tarea completada", str(details.get("detail") or "Resultado entregado"), None),
        "error": ("error", "La tarea terminó con un error", str(details.get("detail") or details.get("error") or "Error"), None),
        "timeout": ("error", "La tarea agotó el tiempo configurado", str(details.get("detail") or "Timeout"), None),
    }
    return descriptors.get(phase, ("working", "ADA está trabajando", phase.replace("_", " "), details.get("component")))


def _activity_update(runtime, phase, details=None, session_id=None):
    details = dict(details or {})
    lock = runtime.setdefault("activity_lock", threading.RLock())
    now = time.time()
    with lock:
        state = runtime.setdefault("activity", _new_activity_state())
        status_value, label, detail, component = _activity_descriptor(phase, details)

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
            state.setdefault("execution_steps", []).append({
                "phase": phase,
                "server": details.get("server"),
                "tool": details.get("tool"),
                "ok": details.get("ok"),
                "at": now,
            })

        trace_entry = {
            "phase": phase,
            "label": label,
            "detail": detail[:300],
            "status": status_value,
            "component": component,
            "model": state.get("model"),
            "role": state.get("role"),
            "extra": {k: v for k, v in details.items() if k not in {"message", "detail"} and isinstance(v, (str, int, float, bool, list, dict))},
            "at": now,
        }

        trace = list(state.get("trace") or [])
        trace.append(trace_entry)
        state["trace"] = trace[-30:]

        state.update({
            "status": status_value, "phase": phase, "label": label,
            "detail": detail[:500], "component": component,
            "session_id": session_id or state.get("session_id"), "updated_at": now,
        })
        recent = list(state.get("recent") or [])
        recent.append({"phase": phase, "label": label, "detail": detail[:180], "status": status_value, "at": now})
        state["recent"] = recent[-12:]

        # When a task finishes, record it into the completed task history archive
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


def _activity_snapshot(runtime):
    lock = runtime.setdefault("activity_lock", threading.RLock())
    with lock:
        snapshot = dict(runtime.setdefault("activity", _new_activity_state()))
        snapshot["recent"] = [dict(item) for item in snapshot.get("recent") or []]
        snapshot["trace"] = [dict(item) for item in snapshot.get("trace") or []]
    with _task_history_lock:
        history = [dict(item) for item in _task_history[:10]]
    snapshot["history"] = history
    if snapshot.get("status") == "complete" and time.time() - float(snapshot.get("updated_at") or 0) > 8:
        snapshot.update({"status": "idle", "phase": "idle", "label": "ADA está lista", "detail": "Esperando una tarea", "component": None})
    return snapshot


chat_executor = ThreadPoolExecutor(max_workers=_chat_workers(cfg), thread_name_prefix="ada-chat")
healthcheck_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ada-healthcheck")


app.extensions["ada_runtime"] = {
    "cfg": cfg,
    "config_path": cfg_path,
    "agent": agent,
    "web_chat": web_chat,
    "session_states": session_states,
    "session_states_lock": session_states_lock,
    "chat_executor": chat_executor,
    "healthcheck_executor": healthcheck_executor,
    "ollama_client": ollama_client,
    "model_catalog": model_catalog,
    "model_benchmark": model_benchmark,
    "mcp_manager": mcp_manager,
    "trigger_manager": trigger_manager,
    "memory_refiner": memory_refiner,
    "identity": {"version": ADA_VERSION, "started_at": PROCESS_STARTED_AT, "reloaded_at": None, "hot_reload": False, "pid": os.getpid()},
    "agent_enabled": True,
    "debug_enabled": False,
    "debug_log": DebugLog(cfg.get("debug_log_path", str(Path.home() / "Desktop/ADA_Data/debug-log.db"))),
    "activity": _new_activity_state(),
    "activity_lock": threading.RLock(),
}


def _runtime():
    """Return the dependencies associated with the current Flask application."""
    runtime = current_app.extensions.get(
        "ada_runtime",
        {
            "cfg": cfg,
            "agent": agent,
            "web_chat": web_chat,
            "session_states": session_states,
            "session_states_lock": session_states_lock,
            "chat_executor": chat_executor,
            "ollama_client": ollama_client,
            "model_catalog": model_catalog,
            "model_benchmark": model_benchmark,
            "mcp_manager": mcp_manager,
            "trigger_manager": trigger_manager,
        },
    )
    # Debug mode is persisted in debug-log.db so the UI and chat endpoints
    # cannot disagree after a reload or when the stream uses another request
    # context.
    if runtime.get("debug_log") is not None:
        runtime["debug_enabled"] = runtime["debug_log"].enabled()
    return runtime


def _log_lifecycle(runtime, component, action, result=None):
    """Always persist service power-state transitions for auditability."""
    if runtime.get("debug_log"):
        runtime["debug_log"].write(
            "lifecycle",
            {"component": component, "action": action, "result": result or {}, "source": "manager"},
            session_id=None,
        )


def _session_state():
    runtime = _runtime()
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
        return runtime["session_states"].setdefault(session_id, WebSessionState(runtime["agent"].mem, session_id))


@app.after_request
def set_session_cookie(response):
    session_id = getattr(g, "ada_session_id", None)
    if session_id and not request.cookies.get("ada_session"):
        response.set_cookie("ada_session", session_id, samesite="Strict", secure=False, httponly=True)
    return response


# ==============================================================================
# Base & SPA Routes
# ==============================================================================

@app.route("/")
def index():
    response = send_from_directory(str(DASHBOARD_DIR), "index.html")
    response.set_cookie("ada_csrf", _csrf_token(), samesite="Strict", secure=False)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


@app.route("/api/health")
def health():
    return jsonify({"status": "healthy", "version": ADA_VERSION, "timestamp": time.time()})


@app.route("/api/status")
def status():
    """Return active engines, local runtime health, and agent registry."""
    runtime = _runtime()
    active_agent = runtime["agent"]
    ollama = runtime.get("ollama_client") or OllamaClient()
    ollama_health = ollama.health()
    # Do not call LocalModelRuntime.ensure_ready() when Ollama is offline: it
    # can perform retries/model discovery and make the dashboard appear frozen.
    if ollama_health.get("online"):
        runtime_info = active_agent.model_manager.runtime_status()
        engines = active_agent.model_manager.available()
        models = active_agent.model_manager.model_catalog()
        recommendations = active_agent.model_manager.model_recommendations()
    else:
        runtime_info = {"provider": "ollama", "endpoint": ollama.endpoint, "available": False, "reason": "ollama_offline"}
        engines = {"local": False, "ollama": False, "openai": False, "anthropic": False, "gpt4all": False}
        models = []
        recommendations = {"adaptive": False, "roles": {}, "model_stats": {}, "telemetry": {}}
    runtime_dict = dict(runtime_info)
    if isinstance(runtime_info.get("status"), dict):
        runtime_dict["available"] = runtime_info["status"].get("available", False) or ollama_health.get("online", False)
        runtime_dict["endpoint"] = runtime_info["status"].get("endpoint", ollama.endpoint)
    else:
        runtime_dict["available"] = ollama_health.get("online", False)

    return jsonify(
        {
            "identity": runtime.get("identity", {"version": ADA_VERSION, "started_at": PROCESS_STARTED_AT, "reloaded_at": None, "hot_reload": False, "pid": os.getpid()}),
            "agent_enabled": runtime.get("agent_enabled", True),
            "debug_enabled": runtime.get("debug_enabled", False),
            "mcp_servers": runtime.get("mcp_manager", MCPManager()).list_servers(),
            "engines": engines,
            "runtime": runtime_dict,
            "ollama_health": ollama_health,
            "agents": list(active_agent.coordinator.available_agents()),
            "hardware": hardware_profile(),
            "models": models,
            "model_recommendations": recommendations,
            "metrics": {
                "agent": active_agent.metrics.snapshot(),
                "models": active_agent.model_manager.metrics.snapshot(),
            },
            "metrics_scraper": metrics_scraper_status(),
            "duplicates": detect_duplicates(),
        }
    )


@app.route("/api/core/state")
def core_state_api():
    """Return the live topology and current execution phase for the core view."""
    runtime = _runtime()
    summary = runtime["agent"].model_manager.selection_summary()
    return jsonify({
        "activity": _activity_snapshot(runtime),
        "models": {"mode": summary.get("mode", "manual"), "active": summary.get("active", {})},
        "connectors": {
            "telegram": get_telegram_service_status(),
            "mcps": runtime.get("mcp_manager", MCPManager()).list_servers(),
            "triggers": runtime.get("trigger_manager", trigger_manager).list_triggers(),
        },
        "telemetry": {"scraper": metrics_scraper_status()},
        "server_time": time.time(),
    })


@app.route("/api/metrics")
def metrics_api():
    active_agent = _runtime()["agent"]
    return jsonify({"agent": active_agent.metrics.snapshot(), "models": active_agent.model_manager.metrics.snapshot()})

@app.route("/metrics")
def prometheus_metrics():
    """Prometheus-compatible exposition endpoint; scraping is external."""
    runtime = _runtime(); agent = runtime["agent"]
    lines = ["# TYPE ada_up gauge", "ada_up 1"]
    for namespace, snapshot in (("agent", agent.metrics.snapshot()), ("models", agent.model_manager.metrics.snapshot())):
        for key, value in snapshot.get("counters", {}).items():
            safe = re.sub(r"[^a-zA-Z0-9_]", "_", key)
            lines.append(f'ada_{namespace}_counter{{name="{safe}"}} {float(value)}')
        for key, timing in snapshot.get("timings", {}).items():
            safe = re.sub(r"[^a-zA-Z0-9_]", "_", key)
            lines.append(f'ada_{namespace}_timing_count{{name="{safe}"}} {timing.get("count", 0)}')
            lines.append(f'ada_{namespace}_timing_avg_seconds{{name="{safe}"}} {timing.get("avg_seconds", 0)}')
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")

@app.route("/api/metrics/timeseries")
def metrics_timeseries_api():
    store = TimeSeriesStore()
    hours = max(1, min(24 * 7, int(request.args.get("hours", 24))))
    since = time.time() - hours * 3600
    with __import__('sqlite3').connect(store.path) as db:
        rows = db.execute(
            """
            SELECT ts,name,labels,value
            FROM prometheus_samples
            WHERE ts>=?
              AND name NOT LIKE '%_source_ai_testing%'
              AND name NOT LIKE '%_source_diagnostic%'
            ORDER BY ts ASC
            """,
            (since,),
        ).fetchall()
    samples = [{"ts": r[0], "metric": r[1], "tags": r[2], "value": r[3], "component": (r[2].split('=')[1].strip('"') if 'component=' in r[2] else "ada")} for r in rows]
    scraper = metrics_scraper_status()
    return jsonify({"retention_days": 7, "source": "external_scraper", "last_sample_at": scraper.get("last_sample_at"), "stale": not scraper.get("ok"), "scraper": scraper, "samples": samples})


# ==============================================================================
# HealthDoctor & Auto-Healing Endpoints
# ==============================================================================

@app.route("/api/healthcheck")
def healthcheck_api():
    runtime = _runtime()
    doctor = runtime.get("doctor") or HealthDoctor(
        runtime.get("agent"),
        runtime.get("cfg"),
        runtime.get("mcp_manager") or MCPManager(),
        runtime.get("ollama_client") or OllamaClient(),
    )
    return jsonify(doctor.diagnose())


@app.route("/api/healthcheck/heal", methods=["POST"])
def healthcheck_heal_api():
    runtime = _runtime()
    doctor = runtime.get("doctor") or HealthDoctor(
        runtime.get("agent"),
        runtime.get("cfg"),
        runtime.get("mcp_manager") or MCPManager(),
        runtime.get("ollama_client") or OllamaClient(),
    )
    return jsonify(doctor.auto_heal_all())


@app.route("/api/healthcheck/fix/<action_id>", methods=["POST"])
def healthcheck_fix_api(action_id):
    runtime = _runtime()
    doctor = runtime.get("doctor") or HealthDoctor(
        runtime.get("agent"),
        runtime.get("cfg"),
        runtime.get("mcp_manager") or MCPManager(),
        runtime.get("ollama_client") or OllamaClient(),
    )
    return jsonify(doctor.fix_action(action_id))


# ==============================================================================
# Ollama Endpoints
# ==============================================================================

@app.route("/api/ollama/status")
def ollama_status():
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    active_agent = runtime["agent"]
    health = client.health()
    runtime_info = active_agent.model_manager.runtime_status()
    runtime_dict = dict(runtime_info)
    if isinstance(runtime_info.get("status"), dict):
        runtime_dict["available"] = runtime_info["status"].get("available", False) or health.get("online", False)
    else:
        runtime_dict["available"] = health.get("online", False)

    return jsonify({
        "health": health,
        "runtime": runtime_dict,
    })


@app.route("/api/ollama/models")
def ollama_models():
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    return jsonify({
        "models": client.list_models(),
        "running": client.running_models(),
    })


@app.route("/api/ollama/running")
def ollama_running():
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    return jsonify({
        "running": client.running_models(),
    })


@app.route("/api/ollama/unload", methods=["POST"])
def ollama_unload():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    success = client.unload_model(model_name)
    return jsonify({"ok": success, "model": model_name})


@app.route("/api/ollama/load", methods=["POST"])
def ollama_load():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    cfg_data = runtime.get("cfg", {})
    keep_alive = data.get("keep_alive") or cfg_data.get("ollama_keep_alive", "2m")
    success = client.load_model(model_name, keep_alive=keep_alive)
    return jsonify({"ok": success, "model": model_name})


@app.route("/api/ollama/preload_all", methods=["POST"])
def ollama_preload_all():
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    active_agent = runtime.get("agent")
    cfg_data = runtime.get("cfg", {})
    keep_alive = cfg_data.get("ollama_keep_alive", "2m")

    models_to_load = set()
    if active_agent and hasattr(active_agent, "model_manager"):
        summary = active_agent.model_manager.selection_summary()
        policy = summary.get("policy", {})
        for role, assignment in policy.items():
            if isinstance(assignment, dict):
                pref = assignment.get("preferred")
                if pref:
                    models_to_load.add(pref)
            elif isinstance(assignment, str) and assignment:
                models_to_load.add(assignment)

    # If no policy models found, try all installed models
    if not models_to_load:
        for m in client.list_models():
            if m.get("name"):
                models_to_load.add(m["name"])

    results = {}
    for m_name in models_to_load:
        results[m_name] = client.load_model(m_name, keep_alive=keep_alive)

    return jsonify({
        "ok": any(results.values()) if results else False,
        "loaded": [m for m, ok in results.items() if ok],
        "failed": [m for m, ok in results.items() if not ok],
        "running": client.running_models(),
    })


@app.route("/api/ollama/delete", methods=["POST", "DELETE"])
def ollama_delete():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    success = client.delete_model(model_name)
    return jsonify({"ok": success, "model": model_name})


@app.route("/api/ollama/pull/stream", methods=["POST"])
def ollama_pull_stream():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()

    @stream_with_context
    def progress_events():
        for chunk in client.stream_pull(model_name):
            yield f"event: progress\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'ok': True, 'model': model_name})}\n\n"

    return Response(
        progress_events(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.route("/api/ollama/config", methods=["GET", "POST"])
def ollama_config_api():
    runtime = _runtime()
    active_agent = runtime["agent"]
    cfg_data = runtime.get("cfg", {})
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        candidate = dict(cfg_data)
        if "cpu_limit_percent" in data:
            candidate["cpu_limit_percent"] = max(10, min(100, int(data["cpu_limit_percent"])))
        if "ollama_num_thread" in data:
            val = data["ollama_num_thread"]
            candidate["ollama_num_thread"] = int(val) if val else None
        if "ollama_num_ctx" in data:
            val = data["ollama_num_ctx"]
            candidate["ollama_num_ctx"] = int(val) if val else None
        if "ollama_keep_alive" in data:
            candidate["ollama_keep_alive"] = str(data["ollama_keep_alive"])
        if "ollama_auto_unload" in data:
            candidate["ollama_auto_unload"] = bool(data["ollama_auto_unload"])
        if "ollama_idle_unload_seconds" in data:
            candidate["ollama_idle_unload_seconds"] = max(30, int(data["ollama_idle_unload_seconds"]))
        if "ollama_temperature" in data:
            candidate["ollama_temperature"] = float(data["ollama_temperature"])

        requested_profile = str(data.get("timeout_profile", candidate.get("timeout_profile", "patient"))).lower()
        if requested_profile in TIMEOUT_PRESETS:
            candidate.update(TIMEOUT_PRESETS[requested_profile])
            candidate["timeout_profile"] = requested_profile
        elif requested_profile == "custom":
            candidate["timeout_profile"] = "custom"
            for key in ("router_timeout", "model_timeout", "chat_timeout_seconds", "food_advisor_timeout"):
                if key in data:
                    candidate[key] = float(data[key])
        else:
            return jsonify({"error": "invalid_timeout_profile"}), 400

        try:
            validate_config(candidate)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": "invalid_config", "message": str(exc)}), 400

        cfg_data.clear()
        cfg_data.update(candidate)
        active_agent.cfg = cfg_data
        active_agent.model_manager.reload(cfg_data)
        active_agent.router.config = cfg_data
        active_agent.policy.config = cfg_data
        runtime["web_chat"].config = cfg_data
        target = runtime.get("config_path")
        if target:
            Path(target).write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return jsonify({"ok": True, "config": _ollama_config_payload(cfg_data)})

    return jsonify(_ollama_config_payload(cfg_data))


@app.route("/api/ollama/details")
def ollama_details():
    model_name = request.args.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = _runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    return jsonify(client.show_model(model_name))


# ==============================================================================
# Models & Benchmark Endpoints
# ==============================================================================

@app.route("/api/models/catalog", methods=["GET", "POST", "DELETE"])
def models_catalog_api():
    runtime = _runtime()
    catalog_mgr = runtime.get("model_catalog") or ModelCatalog(runtime.get("cfg"))

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name_required"}), 400
        roles = data.get("roles", ["chat"])
        desc = data.get("description", "")
        tier = data.get("quality_tier", "medium")
        min_ram = float(data.get("min_ram_gb", 4))
        auto_pull = bool(data.get("auto_pull", False))

        result = catalog_mgr.upsert_model(
            name=name,
            roles=roles,
            description=desc,
            quality_tier=tier,
            min_ram_gb=min_ram,
            auto_pull=auto_pull,
        )
        return jsonify({"ok": True, "model": result, "catalog": catalog_mgr.get_catalog()})

    if request.method == "DELETE":
        data = request.get_json(silent=True) or {}
        name = data.get("name") or request.args.get("name")
        if not name:
            return jsonify({"error": "name_required"}), 400
        deleted = catalog_mgr.delete_model_from_catalog(name)
        return jsonify({"ok": deleted, "name": name, "catalog": catalog_mgr.get_catalog()})

    return jsonify({
        "catalog": catalog_mgr.get_catalog(),
        "roles": catalog_mgr.get_roles(),
    })


@app.route("/api/models/policy", methods=["GET", "POST"])
def models_policy_api():
    runtime = _runtime()
    active_agent = runtime["agent"]
    cfg_data = runtime.get("cfg", {})
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        mode = str(data.get("selection_mode") or ("manual" if data.get("model_policy") else "")).lower()
        if mode not in {"manual", "light", "hybrid", "turbo"}:
            return jsonify({"error": "invalid_selection_mode"}), 400
        if mode == "manual":
            new_policy = data.get("manual_policy") or data.get("model_policy")
            if not isinstance(new_policy, dict):
                return jsonify({"error": "invalid_policy"}), 400
        else:
            new_policy = active_agent.model_manager.automatic_policy(mode)

        candidate = dict(cfg_data)
        candidate["model_selection_mode"] = mode
        candidate["model_policy"] = new_policy
        # Cold-start timings are dominated by disk/RAM loading and should not
        # silently rewrite a user's automatic profile.
        candidate["adaptive_models"] = False
        candidate.update(active_agent.model_manager.runtime_settings_for_mode(mode))
        validate_config(candidate)

        cfg_data.clear()
        cfg_data.update(candidate)
        active_agent.cfg = cfg_data
        active_agent.model_manager.reload(cfg_data)
        active_agent.router.config = cfg_data
        active_agent.policy.config = cfg_data
        runtime["web_chat"].config = cfg_data
        runtime["cfg"] = cfg_data
        target = runtime.get("config_path")
        if target:
            Path(target).write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")
        summary = active_agent.model_manager.selection_summary()
        return jsonify({"ok": True, **summary, "manual_policy": cfg_data.get("model_policy", {})})

    summary = active_agent.model_manager.selection_summary()
    return jsonify({
        "models": cfg_data.get("models", {}),
        "model_policy": summary["policy"],
        "manual_policy": cfg_data.get("model_policy", {}),
        **summary,
    })


@app.route("/api/models/benchmark/prompts", methods=["GET"])
def models_benchmark_prompts_api():
    runtime = _runtime()
    bench = runtime.get("model_benchmark") or ModelBenchmark()
    return jsonify({"ok": True, "prompts": bench.get_prompt_catalog()})


@app.route("/api/models/benchmark", methods=["POST"])
def models_benchmark_api():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    prompt_key = data.get("prompt_key", "quick")
    custom_prompt = data.get("custom_prompt")
    run_suite = bool(data.get("run_suite") or prompt_key == "suite")
    prompt_keys = data.get("prompt_keys")

    if not model_name:
        return jsonify({"error": "model_required", "message": "Se requiere especificar un modelo"}), 400

    runtime = _runtime()
    bench = runtime.get("model_benchmark") or ModelBenchmark()

    if run_suite:
        result = bench.run_suite(model_name, prompt_keys=prompt_keys)
    else:
        result = bench.run(model_name, prompt_key=prompt_key, custom_prompt=custom_prompt)

    return jsonify(result)


@app.route("/api/healthcheck/prompts", methods=["GET"])
def healthcheck_prompts_api():
    """Return the functional checklist stored in ADA's SQLite database."""
    store = HealthcheckStore(_runtime()["agent"].mem)
    prompts = store.prompts()
    groups = {}
    for item in prompts:
        groups.setdefault(item.get("functional_category") or functional_category(item.get("category")), []).append(item)
    return jsonify({"ok": True, "prompts": prompts, "groups": groups, "storage": "sqlite"})


@app.route("/api/healthcheck/prompts", methods=["POST"])
def healthcheck_prompt_create_api():
    """Add a read-only case without changing application code."""
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "")
    if re.search(r"\b(borr|elimin|mov|renombr|escrib|creá|crea|env[ií]a|ejecut)\w*\b|\b(compra|vende)\s+(acciones?|cripto|d[oó]lares?)", prompt, re.I):
        return jsonify({"error": "healthcheck_must_be_readonly", "message": "Los casos del healthcheck solo pueden consultar o analizar."}), 400
    try:
        store = HealthcheckStore(_runtime()["agent"].mem)
        store.add_prompt({**data, "prompt": prompt})
    except ValueError as exc:
        return jsonify({"error": "invalid_healthcheck_prompt", "message": str(exc)}), 400
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            return jsonify({"error": "healthcheck_prompt_exists", "message": "Ya existe un caso con ese id."}), 409
        raise
    return jsonify({"ok": True, "id": data.get("id")}), 201


@app.route("/api/healthcheck/history", methods=["GET"])
def healthcheck_history_api():
    store = HealthcheckStore(_runtime()["agent"].mem)
    return jsonify({"ok": True, "runs": store.history()})


def _execute_healthcheck_batch(runtime, prompts, run_id):
    """Run a persisted batch outside the HTTP request so reloads do not lose progress."""
    store = HealthcheckStore(runtime["agent"].mem)
    case_timeout = max(30.0, float((runtime.get("cfg") or {}).get("healthcheck_case_timeout_seconds", 300)))
    for item in prompts:
        store.mark_batch_running(run_id, item["id"])
        started = time.monotonic()
        session_id = f"{run_id}_{item['id']}"
        state = WebSessionState(runtime["agent"].mem, session_id)
        trace = []
        executed_mcps = []

        if not store.batch(run_id) or store.batch(run_id)["status"] != "running":
            return
        def progress(phase, details):
            event = {"phase": phase, **(details or {}), "at_seconds": round(time.monotonic() - started, 3)}
            trace.append(event)
            if phase in {"capability_started", "capability_finished"}:
                server_name = details.get("server") or details.get("capability")
                tool_name = details.get("tool") or details.get("capability")
                if server_name or tool_name:
                    executed_mcps.append({"server": server_name, "tool": tool_name, "ok": details.get("ok")})

        # A model or connector can get stuck without raising an exception.
        # Run each case behind a hard deadline so one stalled case cannot stop
        # the whole checklist. The worker is daemonized because Python cannot
        # safely kill an arbitrary model/tool call in-process.
        outcome = {}

        def invoke_case():
            try:
                result, result_status = runtime["web_chat"].handle(item["prompt"], state, "es", progress=progress)
                outcome.update({"payload": result, "status": result_status})
            except Exception as exc:
                outcome.update({"payload": {}, "status": 500, "error": str(exc)})

        case_thread = threading.Thread(target=invoke_case, name=f"healthcheck-case-{item['id']}", daemon=True)
        case_thread.start()
        case_thread.join(case_timeout)
        if case_thread.is_alive():
            payload, reply, status = {}, "", 504
            error = f"healthcheck_case_timeout_after_{case_timeout:g}s"
            trace.append({"phase": "case_timeout", "timeout_seconds": case_timeout, "at_seconds": round(time.monotonic() - started, 3)})
        else:
            payload = outcome.get("payload") or {}
            status = outcome.get("status", 500)
            reply = payload.get("reply") or payload.get("message") or ""
            error = outcome.get("error") or (payload.get("error") if status >= 400 else None)
        if not error and requires_mcp(item) and not executed_mcps:
            error = "required_mcp_not_executed"
            trace.append({
                "phase": "mcp_required_but_not_executed",
                "category": item.get("category"),
                "at_seconds": round(time.monotonic() - started, 3),
            })
        evaluation = evaluate_healthcheck(item, reply, time.monotonic() - started, error)
        model = payload.get("model") if isinstance(payload, dict) else None
        for event in reversed(trace):
            if event.get("model"):
                model = event["model"]
                break
        if not error and reply:
            cfg = runtime.get("cfg") or {}
            policy = cfg.get("model_policy", {}).get("reasoning", {})
            judge_model = cfg.get("healthcheck_judge_model") or policy.get("preferred") or cfg.get("models", {}).get("chat", "llama3.2:3b")
            judge = llm_judge(item, reply, cfg.get("ollama_url", "http://127.0.0.1:11434"), judge_model)
            evaluation["judge"] = judge
            evaluation["passed"] = bool(judge.get("passed"))
            evaluation["score"] = judge.get("score", 0.0)
            evaluation["issues"] = judge.get("issues", [])
            evaluation["rationale"] = judge.get("rationale", "")
            trace.append({"phase": "judge_finished", "model": judge.get("model"), "source": judge.get("source"), "score": judge.get("score"), "passed": judge.get("passed"), "at_seconds": round(time.monotonic() - started, 3)})
        status_name = "passed" if evaluation["passed"] else ("error" if error else "failed")
        unique_mcps = []
        seen_mcps = set()
        for mcp in executed_mcps:
            key = (mcp.get("server"), mcp.get("tool"))
            if key not in seen_mcps:
                seen_mcps.add(key)
                unique_mcps.append(mcp)
        current_batch = store.batch(run_id)
        if not current_batch or current_batch["status"] != "running":
            return
        store.save_run(run_id, item["id"], reply, evaluation, evaluation["elapsed_seconds"], request=item["prompt"], status=status_name, status_code=status, model=model, mcps=unique_mcps, trace=trace)
        store.mark_batch_item(run_id, evaluation["passed"])
    store.finish_batch(run_id)


_healthcheck_active_run_ids = set()
_healthcheck_active_runs_lock = threading.RLock()


def _healthcheck_active_runs():
    with _healthcheck_active_runs_lock:
        return set(_healthcheck_active_run_ids)


def _recover_orphaned_healthchecks(store):
    return store.recover_orphaned_batches(_healthcheck_active_runs())


@app.route("/api/healthcheck/runs/active", methods=["GET"])
def healthcheck_active_runs_api():
    store = HealthcheckStore(_runtime()["agent"].mem)
    _recover_orphaned_healthchecks(store)
    return jsonify({"ok": True, "runs": store.active_batches()})


@app.route("/api/healthcheck/batches", methods=["GET"])
def healthcheck_batches_api():
    store = HealthcheckStore(_runtime()["agent"].mem)
    _recover_orphaned_healthchecks(store)
    return jsonify({"ok": True, "runs": store.recent_batches()})


@app.route("/api/healthcheck/latest", methods=["GET"])
def healthcheck_latest_api():
    store = HealthcheckStore(_runtime()["agent"].mem)
    return jsonify({"ok": True, "results": store.latest_results()})


@app.route("/api/healthcheck/runs/<run_id>", methods=["GET"])
def healthcheck_run_status_api(run_id):
    store = HealthcheckStore(_runtime()["agent"].mem)
    _recover_orphaned_healthchecks(store)
    batch = store.batch(run_id)
    if not batch:
        return jsonify({"error": "healthcheck_run_not_found"}), 404
    include_history = request.args.get("details", "1").lower() not in {"0", "false", "no"}
    history = [item for item in store.history(200) if item["run_id"] == run_id] if include_history else []
    return jsonify({"ok": True, "run": batch, "history": history})


@app.route("/api/healthcheck/runs/<run_id>/cancel", methods=["POST"])
def healthcheck_run_cancel_api(run_id):
    """Mark a stalled healthcheck as interrupted without killing ADA."""
    store = HealthcheckStore(_runtime()["agent"].mem)
    changed = store.interrupt_batch(run_id)
    with _healthcheck_active_runs_lock:
        _healthcheck_active_run_ids.discard(run_id)
    batch = store.batch(run_id)
    if not batch:
        return jsonify({"error": "healthcheck_run_not_found"}), 404
    return jsonify({"ok": True, "changed": bool(changed), "run": batch})


@app.route("/api/healthcheck/run", methods=["POST"])
def healthcheck_run_api():
    """Create a durable batch and execute it in the background."""
    runtime = _runtime()
    store = HealthcheckStore(runtime["agent"].mem)
    requested = (request.get_json(silent=True) or {}).get("prompt_ids")
    prompts = [p for p in store.prompts() if not requested or p["id"] in requested]
    if not prompts:
        return jsonify({"error": "healthcheck_no_prompts"}), 400
    run_id = f"healthcheck_{int(time.time())}_{secrets.token_hex(4)}"
    store.begin_batch(run_id, [item["id"] for item in prompts])
    with _healthcheck_active_runs_lock:
        _healthcheck_active_run_ids.add(run_id)
    try:
        executor = runtime.get("healthcheck_executor", healthcheck_executor)
        future = executor.submit(_execute_healthcheck_batch, runtime, prompts, run_id)
        def healthcheck_done(done_future):
            with _healthcheck_active_runs_lock:
                _healthcheck_active_run_ids.discard(run_id)
            try:
                done_future.result()
            except Exception:
                app.logger.exception("healthcheck_batch_failed run_id=%s", run_id)
                HealthcheckStore(runtime["agent"].mem).interrupt_batch(run_id)
        future.add_done_callback(healthcheck_done)
    except Exception:
        with _healthcheck_active_runs_lock:
            _healthcheck_active_run_ids.discard(run_id)
        raise
    return jsonify({"ok": True, "accepted": True, "run_id": run_id, "run": store.batch(run_id)}), 202


@app.route("/api/ollama/start", methods=["POST"])
def ollama_start():
    runtime = _runtime(); active_agent = runtime["agent"]
    cfg_file = runtime.get("config_path") or cfg_path
    if cfg_file and Path(cfg_file).is_file():
        try:
            fresh_cfg = load_config(cfg_file, PROJECT_ROOT)
            if fresh_cfg:
                runtime["cfg"] = fresh_cfg
                active_agent.model_manager.reload(fresh_cfg)
        except Exception:
            pass
    else:
        # If no config_path, force reload with current or updated default
        active_agent.model_manager.reload(runtime.get("cfg"))

    status = active_agent.model_manager.local_runtime.start()
    _log_lifecycle(runtime, "ollama", "start", status.as_dict())
    return jsonify({"ok": status.available, "runtime": status.as_dict()})


@app.route("/api/ollama/stop", methods=["POST"])
def ollama_stop():
    runtime = _runtime(); active_agent = runtime["agent"]
    status = active_agent.model_manager.local_runtime.stop()
    _log_lifecycle(runtime, "ollama", "stop", status.as_dict())
    return jsonify({"ok": not status.available, "runtime": status.as_dict()})


@app.route("/api/ollama/restart", methods=["POST"])
def ollama_restart():
    runtime = _runtime(); active_agent = runtime["agent"]
    status = active_agent.model_manager.local_runtime.restart()
    _log_lifecycle(runtime, "ollama", "restart", status.as_dict())
    return jsonify({"ok": status.available, "runtime": status.as_dict()})


@app.route("/api/agent/restart", methods=["POST"])
def agent_restart():
    runtime = _runtime()
    active_agent = runtime["agent"]
    active_agent.model_manager.reload(runtime.get("cfg"))
    runtime["agent_enabled"] = True
    with runtime["session_states_lock"]:
        runtime["session_states"].clear()
    _log_lifecycle(runtime, "agent", "restart", {"enabled": True})
    return jsonify({"ok": True, "message": "Agente ADA reiniciado exitosamente."})

@app.route("/api/agent/stop", methods=["POST"])
def agent_stop():
    runtime = _runtime()
    runtime["agent_enabled"] = False
    _log_lifecycle(runtime, "agent", "stop", {"enabled": False})
    return jsonify({"ok": True, "message": "ADA Agent Core apagado."})

@app.route("/api/agent/start", methods=["POST"])
def agent_start():
    runtime = _runtime()
    runtime["agent_enabled"] = True
    _log_lifecycle(runtime, "agent", "start", {"enabled": True})
    return jsonify({"ok": True, "message": "ADA Agent Core iniciado."})


# ==============================================================================
# MCPs & Tools Endpoints
# ==============================================================================

@app.route("/api/mcps/config", methods=["GET", "POST"])
def mcps_config_api():
    runtime = _runtime()
    manager = runtime.get("mcp_manager") or MCPManager()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        success = manager.save_raw_config(data)
        return jsonify({"ok": success, "config": manager.get_raw_config()})
    return jsonify(manager.get_raw_config())


@app.route("/api/mcps/servers", methods=["GET", "POST"])
def mcps_servers_api():
    runtime = _runtime()
    manager = runtime.get("mcp_manager") or MCPManager()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        transport = data.get("transport", "stdio")
        command = data.get("command")
        url = data.get("url")
        if not name:
            return jsonify({"error": "name_required"}), 400
        server = manager.add_custom_server(name, transport, command, url)
        return jsonify({"ok": True, "server": server})
    return jsonify({"servers": manager.list_servers()})


@app.route("/api/mcps/servers/<name>/start", methods=["POST"])
def mcps_server_start_api(name):
    runtime = _runtime(); manager = runtime.get("mcp_manager") or MCPManager()
    res = manager.start_server(name)
    _log_lifecycle(runtime, f"mcp:{name}", "start", res)
    return jsonify(res)


@app.route("/api/mcps/servers/<name>/stop", methods=["POST"])
def mcps_server_stop_api(name):
    runtime = _runtime(); manager = runtime.get("mcp_manager") or MCPManager()
    res = manager.stop_server(name)
    _log_lifecycle(runtime, f"mcp:{name}", "stop", res)
    return jsonify(res)


@app.route("/api/mcps/servers/<name>/restart", methods=["POST"])
def mcps_server_restart_api(name):
    runtime = _runtime(); manager = runtime.get("mcp_manager") or MCPManager()
    res = manager.restart_server(name)
    _log_lifecycle(runtime, f"mcp:{name}", "restart", res)
    return jsonify(res)


@app.route("/api/mcps/servers/<name>/ping", methods=["POST", "GET"])
def mcps_server_ping_api(name):
    manager = _runtime().get("mcp_manager") or MCPManager()
    res = manager.ping_server(name)
    return jsonify(res)


@app.route("/api/mcps/servers/restart-all", methods=["POST"])
def mcps_servers_restart_all_api():
    runtime = _runtime(); manager = runtime.get("mcp_manager") or MCPManager()
    res = manager.restart_all_servers()
    _log_lifecycle(runtime, "mcps", "restart_all", res)
    return jsonify(res)

@app.route("/api/mcps/servers/stop-all", methods=["POST"])
def mcps_servers_stop_all_api():
    runtime = _runtime(); manager = runtime.get("mcp_manager") or MCPManager()
    results = {name: manager.stop_server(name) for name in list(manager._servers)}
    _log_lifecycle(runtime, "mcps", "stop_all", results)
    return jsonify({"ok": True, "results": results})

@app.route("/api/mcps/servers/start-all", methods=["POST"])
def mcps_servers_start_all_api():
    runtime = _runtime(); manager = runtime.get("mcp_manager") or MCPManager()
    results = {name: manager.start_server(name) for name in list(manager._servers)}
    _log_lifecycle(runtime, "mcps", "start_all", results)
    return jsonify({"ok": True, "results": results})


@app.route("/api/mcps/tools")
def mcps_tools_api():
    runtime = _runtime()
    manager = runtime.get("mcp_manager") or MCPManager()
    category = request.args.get("category")
    return jsonify({"tools": manager.list_tools(category)})


@app.route("/api/mcps/tools/toggle", methods=["POST"])
def mcps_tool_toggle_api():
    data = request.get_json(silent=True) or {}
    tool_name = data.get("name")
    enabled = bool(data.get("enabled", True))
    if not tool_name:
        return jsonify({"error": "tool_name_required"}), 400
    runtime = _runtime()
    manager = runtime.get("mcp_manager") or MCPManager()
    success = manager.toggle_tool(tool_name, enabled)
    return jsonify({"ok": success, "name": tool_name, "enabled": enabled})


@app.route("/api/mcps/tools/run", methods=["POST"])
def mcps_tool_run_api():
    data = request.get_json(silent=True) or {}
    tool_name = data.get("name")
    parameters = data.get("parameters") or {}
    if not tool_name:
        return jsonify({"error": "tool_name_required"}), 400
    runtime = _runtime()
    manager = runtime.get("mcp_manager") or MCPManager()
    active_agent = runtime.get("agent")
    started = time.monotonic()
    active_agent.metrics.increment("tool_invocations", tags={"tool": tool_name})
    result = manager.execute_tool(tool_name, parameters, active_agent)
    active_agent.metrics.observe("tool_response_seconds", time.monotonic() - started, tags={"tool": tool_name, "status": "error" if isinstance(result, dict) and result.get("error") else "ok"})
    return jsonify(result)


# ==============================================================================
# Telegram Bot Service Controller & Endpoints
# ==============================================================================

_telegram_history = []
_telegram_history_lock = threading.Lock()


def _resolve_telegram_token(cfg_data: Optional[Dict[str, Any]] = None) -> str:
    # 1. Check encrypted SecureVault (vault.db)
    try:
        from ada.infrastructure.credentials import SecureVault
        token = SecureVault().get("telegram_bot_token") or SecureVault().get("telegram_token")
        if token:
            return str(token).strip()
    except Exception:
        pass

    # 2. Environment variable
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token

    # 3. Config object
    if cfg_data is None:
        cfg_data = _runtime().get("cfg", {}) if "ada_runtime" in current_app.extensions else load_config(cfg_path, PROJECT_ROOT)
    tg_cfg = cfg_data.get("telegram", {}) if isinstance(cfg_data.get("telegram"), dict) else {}
    token = str(tg_cfg.get("token") or tg_cfg.get("bot_token") or cfg_data.get("telegram_token") or cfg_data.get("telegram_bot_token") or "").strip()
    if token:
        return token
    return ""


def record_telegram_interaction(data: dict, reply: str):
    with _telegram_history_lock:
        meta = data.get("metadata") or {}
        chat_id = str(data.get("chat_id") or meta.get("chat_id") or "")
        username = str(data.get("username") or meta.get("username") or "")
        first_name = str(data.get("first_name") or meta.get("first_name") or "Usuario Telegram")
        conversation_id = str(data.get("conversation_id") or data.get("session_id") or f"telegram_{chat_id}")
        
        item = {
            "id": f"tg_{int(time.time()*1000)}",
            "conversation_id": conversation_id,
            "chat_id": chat_id,
            "username": username if username.startswith("@") or not username else f"@{username}",
            "first_name": first_name,
            "message": data.get("message", ""),
            "reply": reply,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _telegram_history.insert(0, item)
        if len(_telegram_history) > 100:
            _telegram_history.pop()


def get_telegram_service_status() -> Dict[str, Any]:
    runtime = _runtime()
    cfg_data = runtime.get("cfg", {})
    tg_cfg = cfg_data.get("telegram", {}) if isinstance(cfg_data.get("telegram"), dict) else {}
    token = _resolve_telegram_token(cfg_data)
    manager = runtime.get("trigger_manager", trigger_manager)
    status = manager.telegram_status()

    masked_token = None
    if token:
        masked_token = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"

    return {**status,
        "ok": status.get("ok", False) and bool(token),
        "configured": bool(token),
        "token_set": bool(token),
        "token_masked": masked_token,
        "poll_seconds": float(tg_cfg.get("poll_seconds", 2)),
        "allowed_chat_ids": list(tg_cfg.get("allowed_chat_ids", [])),
        "inbox": str(tg_cfg.get("inbox", "~/Desktop/ADA_Data/telegram_inbox")),
        "conversations_count": len(_telegram_history),
    }


def start_telegram_service() -> Dict[str, Any]:
    return _runtime().get("trigger_manager", trigger_manager).start("telegram")


def stop_telegram_service() -> Dict[str, Any]:
    return _runtime().get("trigger_manager", trigger_manager).stop("telegram")


def restart_telegram_service() -> Dict[str, Any]:
    return _runtime().get("trigger_manager", trigger_manager).restart("telegram")


_metrics_scraper_process = None
_metrics_scraper_lock = threading.RLock()


def start_metrics_scraper_service() -> Dict[str, Any]:
    global _metrics_scraper_process
    with _metrics_scraper_lock:
        status = metrics_scraper_status()
        if status.get("ok"):
            return {"ok": True, "message": "El scraper de métricas ya se encuentra activo.", "status": status}

        root = _find_project_root()
        script_path = root / "tools" / "metrics_scraper.py"
        if not script_path.exists():
            return {"ok": False, "error": f"No se encontró el script {script_path}"}

        import subprocess
        import sys
        try:
            # Check if there is already a dead process handle
            if _metrics_scraper_process and _metrics_scraper_process.poll() is None:
                try:
                    _metrics_scraper_process.terminate()
                    _metrics_scraper_process.wait(timeout=2)
                except Exception:
                    pass

            env = os.environ.copy()
            env["PYTHONPATH"] = str(root)
            _metrics_scraper_process = subprocess.Popen(
                [sys.executable, str(script_path), "--interval", "2"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )
            # Give it a second to start
            time.sleep(1.2)
            new_status = metrics_scraper_status()
            return {"ok": True, "message": "Scraper de métricas iniciado", "status": new_status}
        except Exception as exc:
            return {"ok": False, "error": f"Error al iniciar scraper: {exc}"}


def stop_metrics_scraper_service() -> Dict[str, Any]:
    global _metrics_scraper_process
    with _metrics_scraper_lock:
        if _metrics_scraper_process and _metrics_scraper_process.poll() is None:
            _metrics_scraper_process.terminate()
            try:
                _metrics_scraper_process.wait(timeout=3)
            except Exception:
                _metrics_scraper_process.kill()
            _metrics_scraper_process = None
        else:
            # fallback kill if started elsewhere
            import subprocess
            try:
                subprocess.run(["pkill", "-f", "tools/metrics_scraper.py"], capture_output=True, timeout=3)
            except Exception:
                pass
        return {"ok": True, "message": "Scraper de métricas detenido"}


def restart_metrics_scraper_service() -> Dict[str, Any]:
    """Restart the metrics scraper managed by ADA."""
    stop_metrics_scraper_service()
    time.sleep(0.2)
    result = start_metrics_scraper_service()
    result["message"] = "Scraper de métricas reiniciado" if result.get("ok") else result.get("message", "No se pudo reiniciar el scraper")
    return result


@app.route("/api/metrics/scraper/status")
def metrics_scraper_status_api():
    return jsonify(metrics_scraper_status())


@app.route("/api/metrics/scraper/start", methods=["POST"])
def metrics_scraper_start_api():
    return jsonify(start_metrics_scraper_service())


@app.route("/api/metrics/scraper/stop", methods=["POST"])
def metrics_scraper_stop_api():
    return jsonify(stop_metrics_scraper_service())


@app.route("/api/metrics/scraper/restart", methods=["POST"])
def metrics_scraper_restart_api():
    return jsonify(restart_metrics_scraper_service())


@app.route("/api/triggers")
def triggers_api():
    manager = _runtime().get("trigger_manager", trigger_manager)
    return jsonify(manager.summary(reconcile=True))


@app.route("/api/triggers/<trigger_id>/<action>", methods=["POST"])
def trigger_action_api(trigger_id, action):
    manager = _runtime().get("trigger_manager", trigger_manager)
    handlers = {"start": manager.start, "stop": manager.stop, "restart": manager.restart}
    handler = handlers.get(action)
    if not handler:
        return jsonify({"ok": False, "error": "Acción de disparador no válida."}), 404
    result = handler(trigger_id)
    return jsonify(result), (200 if result.get("ok") else 409)


@app.route("/api/telegram/status")
def telegram_status_api():
    return jsonify(get_telegram_service_status())


@app.route("/api/telegram/start", methods=["POST"])
def telegram_start_api():
    return jsonify(start_telegram_service())


@app.route("/api/telegram/stop", methods=["POST"])
def telegram_stop_api():
    return jsonify(stop_telegram_service())


@app.route("/api/telegram/restart", methods=["POST"])
def telegram_restart_api():
    return jsonify(restart_telegram_service())


@app.route("/api/telegram/history")
def telegram_history_api():
    with _telegram_history_lock:
        return jsonify({"ok": True, "messages": list(_telegram_history), "count": len(_telegram_history)})


@app.route("/api/telegram/config", methods=["POST"])
def telegram_config_api():
    runtime = _runtime()
    body = request.get_json(silent=True) or {}
    token = str(body.get("token", "")).strip()
    allowed_chat_ids = body.get("allowed_chat_ids")

    if token:
        from ada.infrastructure.credentials import SecureVault
        SecureVault().set("telegram_bot_token", token, meta={"service": "telegram", "description": "Token oficial de Telegram BotFather"})
        os.environ["TELEGRAM_BOT_TOKEN"] = token

    target_cfg_path = cfg_path
    cfg_data = {}
    if target_cfg_path.is_file():
        try:
            cfg_data = json.loads(target_cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg_data = {}

    if not isinstance(cfg_data.get("telegram"), dict):
        cfg_data["telegram"] = {}

    # Ensure no plaintext token remains in config.json
    cfg_data["telegram"].pop("token", None)
    cfg_data.pop("telegram_token", None)
    cfg_data.pop("telegram_bot_token", None)

    if allowed_chat_ids is not None:
        if isinstance(allowed_chat_ids, str):
            allowed_chat_ids = [s.strip() for s in allowed_chat_ids.split(",") if s.strip()]
        cfg_data["telegram"]["allowed_chat_ids"] = allowed_chat_ids

    cfg_data["telegram"]["enabled"] = True
    target_cfg_path.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")

    runtime["cfg"]["telegram"] = dict(cfg_data["telegram"])
    runtime.get("trigger_manager", trigger_manager).config = runtime["cfg"]

    return jsonify({"ok": True, "message": "Token cifrado con AES-256 en SecureVault (vault.db) y configuración actualizada", "status": get_telegram_service_status()})


# ==============================================================================
# Secure Vault Management Endpoints (Encrypted SQLite vault.db)
# ==============================================================================

@app.route("/api/vault/keys")
def vault_keys_api():
    from ada.infrastructure.credentials import SecureVault
    try:
        vault = SecureVault()
        keys = vault.list_keys()
        return jsonify({"ok": True, "keys": keys, "vault_path": str(vault.path)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/vault/set", methods=["POST"])
def vault_set_api():
    from ada.infrastructure.credentials import SecureVault
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    value = body.get("value")
    meta = body.get("meta") or {}
    if not name:
        return jsonify({"ok": False, "error": "El nombre del secreto es requerido"}), 400
    if value is None or value == "":
        return jsonify({"ok": False, "error": "El valor del secreto no puede estar vacío"}), 400
    try:
        vault = SecureVault()
        vault.set(name, value, meta=meta)
        return jsonify({"ok": True, "message": f"Secreto '{name}' cifrado con éxito en vault.db"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/vault/<name>", methods=["DELETE"])
def vault_delete_api(name):
    from ada.infrastructure.credentials import SecureVault
    try:
        vault = SecureVault()
        deleted = vault.delete(name)
        if deleted:
            return jsonify({"ok": True, "message": f"Secreto '{name}' eliminado de la bóveda"})
        return jsonify({"ok": False, "error": f"Secreto '{name}' no encontrado"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/telegram/test", methods=["POST"])
def telegram_test_api():
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip() or _resolve_telegram_token()
    if not token:
        return jsonify({"ok": False, "error": "TELEGRAM_BOT_TOKEN no configurado"}), 400
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url, headers={"User-Agent": "ADA-Hub"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return jsonify({"ok": True, "bot": data.get("result"), "token_masked": token[:6] + "..." + token[-4:] if len(token) > 10 else "***"})
            return jsonify({"ok": False, "error": data.get("description", "Error de Telegram")})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ==============================================================================
# Memory & Audit Endpoints
# ==============================================================================

@app.route("/api/audit")
def audit_api():
    limit = min(200, max(1, request.args.get("limit", default=50, type=int)))
    entries = _runtime()["agent"].mem.recent_audit(limit)
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/api/memory/stats")
def memory_stats_api():
    runtime = _runtime()
    active_agent = runtime["agent"]
    audit_entries = active_agent.mem.recent_audit(100)
    sessions = ["main"]
    return jsonify({
        "audit_count": len(audit_entries),
        "recent_audit": audit_entries[:15],
        "sessions": sessions,
        "db_path": getattr(active_agent.mem, "db_path", "memory.db"),
    })


@app.route("/api/memory/refine", methods=["POST"])
def memory_refine_api():
    """Trigger an immediate memory & context refinement pass."""
    runtime = _runtime()
    refiner = runtime.get("memory_refiner")
    if not refiner:
        active_agent = runtime["agent"]
        refiner = MemoryRefiner(active_agent.mem, agent=active_agent, config=runtime.get("cfg", {}))
    result = refiner.refine_cycle()
    return jsonify({"ok": True, "result": result})


# ==============================================================================
# Config & Events Endpoints
# ==============================================================================

@app.route("/api/config", methods=["GET", "POST"])
def config_api():
    runtime = _runtime()
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        candidate = payload.get("config")
        if not isinstance(candidate, dict):
            return jsonify({"error": "invalid_config_payload"}), 400
        validate_config(candidate)
        runtime["cfg"] = candidate
        runtime["agent"].cfg = candidate
        runtime["agent"].model_manager.reload(candidate)
        runtime.get("trigger_manager", trigger_manager).config = candidate
        return jsonify({"ok": True, "config": candidate})
    safe_config = dict(runtime.get("cfg", {}))
    # sanitize sensitive paths / keys if needed
    return jsonify({"config": safe_config})


@app.route("/api/warmup", methods=["POST"])
def warmup():
    return jsonify({"runtime": _runtime()["agent"].model_manager.runtime_status(), "ok": True})

@app.route("/api/debug", methods=["GET", "POST"])
def debug_api():
    runtime = _runtime()
    if request.method == "POST":
        runtime["debug_enabled"] = bool((request.get_json(silent=True) or {}).get("enabled", False))
        runtime["debug_log"].set_enabled(runtime["debug_enabled"])
        runtime["debug_log"].write("debug_mode_changed", {"enabled": runtime["debug_enabled"]}, level="INFO")
    return jsonify({"enabled": runtime.get("debug_enabled", False), "path": runtime["debug_log"].path})

@app.route("/api/restart-all", methods=["POST"])
def restart_all():
    runtime = _runtime()
    manager = runtime.get("mcp_manager") or MCPManager()
    mcp_result = manager.restart_all_servers()
    ollama_status = runtime["agent"].model_manager.local_runtime.restart()
    runtime["agent"].model_manager.reload(runtime.get("cfg"))
    managed_triggers = runtime.get("trigger_manager", trigger_manager)
    telegram_state = managed_triggers.telegram_status()
    trigger_result = (
        managed_triggers.restart("telegram")
        if telegram_state.get("desired_state") == "running"
        else {"ok": True, "message": "Telegram permanece detenido por configuración"}
    )
    runtime["agent_enabled"] = True
    with runtime["session_states_lock"]:
        runtime["session_states"].clear()
    result = {
        "mcps": mcp_result,
        "ollama": ollama_status.as_dict(),
        "agent": {"enabled": True, "reloaded": True},
        "triggers": {"telegram": trigger_result},
    }
    ok = bool(mcp_result.get("ok", True)) and bool(ollama_status.available) and bool(trigger_result.get("ok"))
    _log_lifecycle(runtime, "system", "restart_all", {"ok": ok, **result})
    return jsonify({"ok": ok, **result})


@app.route("/api/models/reload", methods=["POST"])
def reload_models():
    """Apply a validated model policy without rebuilding the running agent."""
    runtime = _runtime()
    runtime.setdefault("identity", {})["reloaded_at"] = datetime.now(timezone.utc).isoformat()
    active_agent = runtime["agent"]
    previous = dict(getattr(active_agent, "cfg", {}))
    payload = request.get_json(silent=True) or {}
    candidate = payload.get("config")
    if not isinstance(candidate, dict):
        candidate = {**previous, **load_config(cfg_path, PROJECT_ROOT)}
    else:
        candidate = {**previous, **candidate}
    validate_config(candidate)
    immutable_keys = {
        "db_path",
        "allowed_roots",
        "memory_encryption",
        "food_profile",
        "photo_root",
        "knowledge_files",
    }
    changed_immutable = [key for key in immutable_keys if key in previous and candidate.get(key) != previous[key]]
    if changed_immutable:
        return jsonify({"error": "immutable_runtime_config", "keys": sorted(changed_immutable)}), 400
    try:
        active_agent.model_manager.reload(candidate)
        selected = active_agent.model_manager.select_model("chat")
        active_agent.cfg = candidate
        active_agent.policy.config = candidate
        active_agent.router.config = candidate
        runtime["cfg"] = candidate
        runtime["web_chat"].config = candidate
    except Exception:
        active_agent.model_manager.reload(previous)
        raise
    return jsonify({"ok": True, "model": selected, "adaptive": bool(candidate.get("adaptive_models", False))})


@app.route("/api/events", methods=["POST"])
def publish_event_api():
    """Receive authenticated Tasker/mobile events into the durable event bus."""
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic") or "").strip()
    payload = data.get("payload")
    if not topic or len(topic) > 128 or not isinstance(payload, dict):
        return jsonify({"error": "invalid_event"}), 400
    runtime = _runtime()
    event_id = runtime["agent"].mem.publish_event(
        topic,
        payload,
        priority=int(data.get("priority", 0)),
        dedupe_key=data.get("dedupe_key"),
        delay_seconds=max(0, int(data.get("delay_seconds", 0))),
    )
    return jsonify({"ok": True, "event_id": event_id, "topic": topic}), 202


@app.route("/api/conversation", methods=["GET", "DELETE"])
def conversation_api():
    state = _session_state()
    with state.lock:
        if request.method == "DELETE":
            state.conversation.clear()
            state.pending_action = None
            state.pending_path_action = None
            state.current_path = None
            state.last_result = None
            if hasattr(_runtime()["agent"].mem, "clear_folder_context"):
                _runtime()["agent"].mem.clear_folder_context(state.session_id)
            return jsonify({"ok": True, "messages": []})
        return jsonify({"messages": list(state.conversation), "count": len(state.conversation)})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    request_started = time.monotonic()
    runtime = _runtime()
    telemetry = runtime["agent"].metrics
    source = str(data.get("source") or "web")
    telemetry.increment("messages_received", tags={"source": source})
    telemetry.increment("chat_invocations", tags={"source": source})
    if not runtime.get("agent_enabled", True):
        return jsonify({"error": "agent_disabled", "message": "ADA Agent Core está apagado."}), 503
    state = _session_state()
    debug = runtime.get("debug_log") if runtime.get("debug_enabled") else None
    if debug:
        debug.write("chat_request", {"message": data.get("message", ""), "lang": data.get("lang"), "source": data.get("source")}, session_id=state.session_id)

    def progress(phase, details):
        activity_details = dict(details)
        if phase == "router_model_started": telemetry.increment("router_invocations", tags={"source": source})
        elif phase == "model_started": telemetry.increment("model_invocations", tags={"model": str(details.get("model") or "unknown")})
        elif phase == "capability_started": telemetry.increment("capability_invocations", tags={"capability": str(details.get("capability") or "unknown")})
        if phase == "received":
            activity_details["channel"] = data.get("source") or "web"
        _activity_update(runtime, phase, activity_details, session_id=state.session_id)
        if debug:
            debug.write("chat_phase", {"phase": phase, **details}, session_id=state.session_id)

    with state.lock:
        payload, status_code = runtime["web_chat"].handle(data.get("message", ""), state, data.get("lang"), progress=progress)
    telemetry.observe("chat_response_seconds", time.monotonic() - request_started, tags={"source": source, "status": "error" if payload.get("error") else "ok"})
    telemetry.increment("chat_errors" if payload.get("error") else "chat_successes", tags={"source": source})
    _activity_update(
        runtime,
        "error" if payload.get("error") else "completed",
        {"detail": payload.get("message") or payload.get("reply") or payload.get("error")},
        session_id=state.session_id,
    )
    if debug:
        debug.write(
            "chat_result",
            {"status_code": status_code, "duration_ms": round((time.monotonic() - request_started) * 1000), "payload": payload},
            session_id=state.session_id,
        )
    if data.get("source") == "telegram" or str(data.get("session_id", "")).startswith("telegram_"):
        try:
            raw_reply = payload.get("reply", "") or payload.get("message", "")
            # Ensure reply is always a human-readable string, not a raw dict
            if not isinstance(raw_reply, str):
                from ada.application.services.responses import text_from_result
                raw_reply = text_from_result(raw_reply)
            record_telegram_interaction(data, raw_reply)
        except Exception:
            pass
    return jsonify(payload), status_code


def _sse(event, payload):
    """Encode one chat progress event for the web client."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _run_chat_in_worker(data, session_id, runtime_app, progress_queue):
    """Execute chat in an isolated context while forwarding real phases."""
    with runtime_app.test_request_context(
        "/api/chat", method="POST", json=data, headers={"Cookie": f"ada_session={session_id}"}
    ):
        runtime = _runtime()
        state = _session_state()
        debug = runtime.get("debug_log") if runtime.get("debug_enabled") else None

        def progress(phase, details):
            event = {"phase": phase, **details}
            progress_queue.put(event)
            activity_details = dict(details)
            if phase == "received":
                activity_details["channel"] = data.get("source") or "web"
            _activity_update(runtime, phase, activity_details, session_id=state.session_id)
            if debug:
                debug.write("chat_phase", event, session_id=state.session_id)

        with state.lock:
            payload, _ = runtime["web_chat"].handle(data.get("message", ""), state, data.get("lang"), progress=progress)
        return payload


def _progress_text(event):
    phase = event.get("phase")
    if phase == "received":
        return "[request] mensaje recibido; iniciando ejecución..."
    if phase == "route_local":
        return f"[router] ruta local seleccionada: filesystem.{event.get('action')}"
    if phase == "route_rule":
        return f"[router] intención resuelta localmente: {event.get('action')}"
    if phase == "folder_resolver_started":
        return f"[FolderResolver] buscando desde {event.get('context_path') or 'base_dir'}..."
    if phase == "folder_resolver_finished":
        if event.get("status") == "resolved":
            return f"[FolderResolver] resuelto por {event.get('source')}: {event.get('path')} ({event.get('elapsed_ms', 0)} ms)"
        return f"[FolderResolver] resultado: {event.get('status')} ({event.get('elapsed_ms', 0)} ms)"
    if phase == "router_model_started":
        return "[router] consultando clasificador de intención..."
    if phase == "router_model_finished":
        return f"[router] intención: {event.get('action')}"
    if phase == "model_started":
        return f"[modelo] usando {event.get('model') or 'modelo local'} para {event.get('role') or 'chat'}..."
    if phase == "model_finished":
        return f"[modelo] {event.get('model') or 'modelo local'} terminó la respuesta"
    if phase == "capability_started":
        payload = event.get("payload") or {}
        server = event.get("server") or ""
        server_txt = f" ({server})" if server else ""
        action_or_tool = event.get("tool") or event.get("capability") or payload.get("action") or "ejecutar"
        target = payload.get("dir") or payload.get("path") or payload.get("query") or payload.get("time_min") or ""
        target_txt = f" en {target}" if target else ""
        return f"[herramienta] ejecutando {action_or_tool}{server_txt}{target_txt}..."
    if phase == "capability_finished":
        action_or_tool = event.get("tool") or event.get("capability") or "Herramienta"
        status_txt = "completada con éxito" if event.get("ok") else f"error ({event.get('error') or 'falló'})"
        return f"[herramienta] {action_or_tool} {status_txt}"
    if phase == "folder_index_updated":
        return f"[memory] índice actualizado: {event.get('indexed', 0)} carpetas aprendidas en {event.get('parent')}"
    return f"[runtime] {phase}"


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Answer through SSE so the UI can show ADA's progress incrementally."""
    data = request.get_json() or {}
    text = data.get("message", "")
    request_started = time.monotonic()
    if not text:
        return jsonify({"error": "empty message"}), 400
    state = _session_state()
    debug = _runtime().get("debug_log") if _runtime().get("debug_enabled") else None
    if debug:
        debug.write("chat_request", {"message": text, "lang": data.get("lang"), "source": data.get("source")}, session_id=state.session_id)
    if not _runtime().get("agent_enabled", True):
        return jsonify({"error": "agent_disabled", "message": "ADA Agent Core está apagado."}), 503

    @stream_with_context
    def events():
        progress_queue = Queue()
        future = _runtime()["chat_executor"].submit(
            _run_chat_in_worker,
            data,
            state.session_id,
            current_app._get_current_object(),  # type: ignore[attr-defined]
            progress_queue,
        )
        try:
            last_update = time.monotonic()
            started_at = last_update
            hard_timeout = max(5, float(_runtime().get("cfg", {}).get("chat_timeout_seconds", 900)))
            while not future.done():
                while True:
                    try:
                        phase_event = progress_queue.get_nowait()
                    except Empty:
                        break
                    yield _sse("status", {"text": _progress_text(phase_event)})
                if time.monotonic() - started_at >= hard_timeout:
                    future.cancel()
                    timeout_minutes = hard_timeout / 60
                    timeout_label = f"{timeout_minutes:g} minutos" if hard_timeout >= 60 else f"{int(hard_timeout)} segundos"
                    timeout_message = f"La tarea superó el límite configurado de {timeout_label} y fue cancelada. Podés ampliarlo desde Motor local → Paciencia del agente."
                    _activity_update(_runtime(), "timeout", {"detail": timeout_message}, session_id=state.session_id)
                    if debug:
                        debug.write("chat_timeout", {"timeout_seconds": hard_timeout, "message": text}, session_id=state.session_id, level="ERROR")
                    yield _sse("error", {"text": timeout_message})
                    yield _sse("done", {"ok": False})
                    return
                if time.monotonic() - last_update >= 3:
                    update = "[runtime] esperando respuesta del modelo/capability; worker activo..."
                    yield _sse("status", {"text": update})
                    last_update = time.monotonic()
                time.sleep(0.25)
            while True:
                try:
                    phase_event = progress_queue.get_nowait()
                except Empty:
                    break
                yield _sse("status", {"text": _progress_text(phase_event)})
            payload = future.result()
            _activity_update(
                _runtime(),
                "error" if payload.get("error") else "completed",
                {"detail": payload.get("message") or payload.get("reply") or payload.get("error")},
                session_id=state.session_id,
            )
            if debug:
                debug.write(
                    "chat_result",
                    {"duration_ms": round((time.monotonic() - request_started) * 1000), "payload": payload},
                    session_id=state.session_id,
                )
            if payload.get("error"):
                yield _sse("error", {"text": payload.get("message") or payload["error"]})
            else:
                yield _sse("reply", {"text": payload.get("reply", "(sin respuesta)")})
        except Exception as error:
            current_app.logger.exception("Streaming chat failed")
            if debug:
                debug.write("chat_error", {"message": str(error), "request": text}, session_id=state.session_id, level="ERROR")
            failure = f"La tarea terminó con un error: {error}"
            _activity_update(_runtime(), "error", {"detail": failure}, session_id=state.session_id)
            state.conversation.extend([{"role": "assistant", "text": failure, "kind": "error"}])
            yield _sse("error", {"text": failure})
        yield _sse("done", {"ok": True})

    response_stream = events()  # type: ignore[call-arg]
    return Response(
        response_stream,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def create_app(config=None, agent_instance=None):
    """Create an isolated Flask application with injectable ADA dependencies."""
    runtime_cfg = dict(config) if isinstance(config, dict) else load_config(cfg_path, PROJECT_ROOT)
    runtime_app = Flask(__name__, static_folder=str(DASHBOARD_DIR), static_url_path="/static")
    ollama_cli = OllamaClient(runtime_cfg.get("ollama_url", "http://127.0.0.1:11434"))
    mcp_mgr = MCPManager(runtime_cfg)
    runtime_agent = agent_instance or Agent(runtime_cfg, mcp_manager=mcp_mgr)
    if agent_instance is not None:
        runtime_agent.mcp_manager = mcp_mgr
        if hasattr(runtime_agent, "prompt_builder"):
            runtime_agent.prompt_builder.mcp_manager = mcp_mgr
    trigger_mgr = TriggerManager(
        runtime_cfg,
        PROJECT_ROOT,
        config_path=None if isinstance(config, dict) else cfg_path,
        state_dir=runtime_cfg.get("trigger_state_dir"),
        internal_url=f"http://127.0.0.1:{int(os.environ.get('ADA_UI_PORT', '5005'))}",
        discover_existing=runtime_cfg.get("discover_external_triggers", True),
    )
    mem_refiner = MemoryRefiner(runtime_agent.mem, agent=runtime_agent, config=runtime_cfg)
    runtime_app.extensions["ada_runtime"] = {
        "cfg": runtime_cfg,
        "config_path": None if isinstance(config, dict) else cfg_path,
        "agent": runtime_agent,
        "web_chat": WebChatService(runtime_agent, runtime_cfg, mcp_manager=mcp_mgr),
        "session_states": {},
        "session_states_lock": threading.RLock(),
        "chat_executor": ThreadPoolExecutor(max_workers=_chat_workers(runtime_cfg), thread_name_prefix="ada-chat"),
        "healthcheck_executor": ThreadPoolExecutor(max_workers=1, thread_name_prefix="ada-healthcheck"),
        "ollama_client": ollama_cli,
        "model_catalog": ModelCatalog(runtime_cfg),
        "model_benchmark": ModelBenchmark(runtime_cfg.get("ollama_url", "http://127.0.0.1:11434")),
        "mcp_manager": mcp_mgr,
        "trigger_manager": trigger_mgr,
        "memory_refiner": mem_refiner,
        "doctor": HealthDoctor(runtime_agent, runtime_cfg, mcp_mgr, ollama_cli),
        "identity": {"version": ADA_VERSION, "started_at": datetime.now(timezone.utc).isoformat(), "reloaded_at": None, "hot_reload": False, "pid": os.getpid()},
        "agent_enabled": True,
        "debug_enabled": False,
        "debug_log": DebugLog(runtime_cfg.get("debug_log_path", str(Path.home() / "Desktop/ADA_Data/debug-log.db"))),
        "activity": _new_activity_state(),
        "activity_lock": threading.RLock(),
    }
    runtime_app.before_request(protect_mutating_requests)
    runtime_app.after_request(hide_provider_metadata)
    runtime_app.after_request(set_session_cookie)
    runtime_app.register_error_handler(Exception, handle_unexpected_error)
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        methods = sorted((rule.methods or set()) - {"HEAD", "OPTIONS"})
        runtime_app.add_url_rule(
            rule.rule,
            endpoint=rule.endpoint,
            view_func=app.view_functions[rule.endpoint],
            methods=methods,
        )
    return runtime_app


def main():
    port = int(os.environ.get("ADA_UI_PORT", "5005"))
    trigger_manager.internal_url = f"http://127.0.0.1:{port}"
    trigger_manager.reconcile()
    trigger_manager.start_watchdog()
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
