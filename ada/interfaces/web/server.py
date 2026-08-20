from flask import Flask, current_app, request, jsonify, send_from_directory, Response, stream_with_context, g
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

from ada.application.agent import Agent
from ada.application.services.web_chat import WebChatService
from ada.config import load_config, validate_config
from ada.infrastructure.runtime.resources import hardware_profile
from ada.interfaces.i18n import tr
from ada.ollama.client import OllamaClient
from ada.models.catalog import ModelCatalog
from ada.models.benchmark import ModelBenchmark
from ada.mcps.manager import MCPManager
from ada.interfaces.web.doctor import HealthDoctor
import re
import secrets
import threading

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
        if (request.content_type or "").split(";", 1)[0].lower() != "application/json":
            return jsonify({"error": "content_type_must_be_json"}), 415
        token = request.headers.get("X-ADA-Token")
        if not token or not secrets.compare_digest(token, request.cookies.get("ada_csrf", "")):
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


cfg_path = PROJECT_ROOT / "config.json"
cfg = load_config(cfg_path, PROJECT_ROOT)

agent = Agent(cfg)
web_chat = WebChatService(agent, cfg)
ollama_client = OllamaClient(cfg.get("ollama_url", "http://127.0.0.1:11434"))
model_catalog = ModelCatalog(cfg)
model_benchmark = ModelBenchmark(cfg.get("ollama_url", "http://127.0.0.1:11434"))
mcp_manager = MCPManager(cfg)


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
        self.lock = threading.RLock()


session_states: Dict[str, WebSessionState] = {}
session_states_lock = threading.RLock()


def _chat_workers(config):
    configured = config.get("chat_workers")
    if configured is not None:
        return max(1, min(32, int(configured)))
    return max(2, min(8, os.cpu_count() or 2))


chat_executor = ThreadPoolExecutor(max_workers=_chat_workers(cfg), thread_name_prefix="ada-chat")


app.extensions["ada_runtime"] = {
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
}


def _runtime():
    """Return the dependencies associated with the current Flask application."""
    return current_app.extensions.get(
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
        },
    )


def _session_state():
    runtime = _runtime()
    session_id = request.cookies.get("ada_session") or getattr(g, "ada_session_id", None)
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


@app.route("/api/status")
def status():
    """Return active engines, local runtime health, and agent registry."""
    runtime = _runtime()
    active_agent = runtime["agent"]
    ollama = runtime.get("ollama_client") or OllamaClient()
    ollama_health = ollama.health()
    runtime_info = active_agent.model_manager.runtime_status()
    runtime_dict = dict(runtime_info)
    if isinstance(runtime_info.get("status"), dict):
        runtime_dict["available"] = runtime_info["status"].get("available", False) or ollama_health.get("online", False)
        runtime_dict["endpoint"] = runtime_info["status"].get("endpoint", ollama.endpoint)
    else:
        runtime_dict["available"] = ollama_health.get("online", False)

    return jsonify(
        {
            "engines": active_agent.model_manager.available(),
            "runtime": runtime_dict,
            "ollama_health": ollama_health,
            "agents": list(active_agent.coordinator.available_agents()),
            "hardware": hardware_profile(),
            "models": active_agent.model_manager.model_catalog(),
            "model_recommendations": active_agent.model_manager.model_recommendations(),
            "metrics": {
                "agent": active_agent.metrics.snapshot(),
                "models": active_agent.model_manager.metrics.snapshot(),
            },
        }
    )


@app.route("/api/metrics")
def metrics_api():
    active_agent = _runtime()["agent"]
    return jsonify({"agent": active_agent.metrics.snapshot(), "models": active_agent.model_manager.metrics.snapshot()})


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


# ==============================================================================
# Models & Benchmark Endpoints
# ==============================================================================

@app.route("/api/models/catalog")
def models_catalog_api():
    runtime = _runtime()
    catalog_mgr = runtime.get("model_catalog") or ModelCatalog(runtime.get("cfg"))
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
        new_policy = data.get("model_policy")
        if isinstance(new_policy, dict):
            cfg_data["model_policy"] = new_policy
            active_agent.model_manager.reload(cfg_data)
            return jsonify({"ok": True, "model_policy": new_policy})
        return jsonify({"error": "invalid_policy"}), 400
    return jsonify({
        "models": cfg_data.get("models", {}),
        "model_policy": cfg_data.get("model_policy", {}),
        "active": {
            "chat": active_agent.model_manager.select_model("chat"),
            "vision": active_agent.model_manager.select_model("vision"),
            "router": active_agent.model_manager.select_model("router"),
        }
    })


@app.route("/api/models/benchmark", methods=["POST"])
def models_benchmark_api():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    prompt_key = data.get("prompt_key", "quick")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = _runtime()
    bench = runtime.get("model_benchmark") or ModelBenchmark()
    result = bench.run(model_name, prompt_key=prompt_key)
    return jsonify(result)


@app.route("/api/ollama/start", methods=["POST"])
def ollama_start():
    active_agent = _runtime()["agent"]
    status = active_agent.model_manager.local_runtime.start()
    return jsonify({"ok": status.available, "runtime": status.as_dict()})


@app.route("/api/ollama/stop", methods=["POST"])
def ollama_stop():
    active_agent = _runtime()["agent"]
    status = active_agent.model_manager.local_runtime.stop()
    return jsonify({"ok": not status.available, "runtime": status.as_dict()})


@app.route("/api/ollama/restart", methods=["POST"])
def ollama_restart():
    active_agent = _runtime()["agent"]
    status = active_agent.model_manager.local_runtime.restart()
    return jsonify({"ok": status.available, "runtime": status.as_dict()})


@app.route("/api/agent/restart", methods=["POST"])
def agent_restart():
    runtime = _runtime()
    active_agent = runtime["agent"]
    active_agent.model_manager.reload(runtime.get("cfg"))
    with runtime["session_states_lock"]:
        runtime["session_states"].clear()
    return jsonify({"ok": True, "message": "Agente ADA reiniciado exitosamente."})


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
    manager = _runtime().get("mcp_manager") or MCPManager()
    res = manager.start_server(name)
    return jsonify(res)


@app.route("/api/mcps/servers/<name>/stop", methods=["POST"])
def mcps_server_stop_api(name):
    manager = _runtime().get("mcp_manager") or MCPManager()
    res = manager.stop_server(name)
    return jsonify(res)


@app.route("/api/mcps/servers/<name>/restart", methods=["POST"])
def mcps_server_restart_api(name):
    manager = _runtime().get("mcp_manager") or MCPManager()
    res = manager.restart_server(name)
    return jsonify(res)


@app.route("/api/mcps/servers/<name>/ping", methods=["POST", "GET"])
def mcps_server_ping_api(name):
    manager = _runtime().get("mcp_manager") or MCPManager()
    res = manager.ping_server(name)
    return jsonify(res)


@app.route("/api/mcps/servers/restart-all", methods=["POST"])
def mcps_servers_restart_all_api():
    manager = _runtime().get("mcp_manager") or MCPManager()
    res = manager.restart_all_servers()
    return jsonify(res)


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
    result = manager.execute_tool(tool_name, parameters, active_agent)
    return jsonify(result)


# ==============================================================================
# Telegram Bot Service Controller & Endpoints
# ==============================================================================

_telegram_listener = None
_telegram_thread = None
_telegram_lock = threading.Lock()


def get_telegram_service_status() -> Dict[str, Any]:
    global _telegram_listener, _telegram_thread
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    cfg_data = _runtime().get("cfg", {}) if "ada_runtime" in current_app.extensions else load_config(cfg_path, PROJECT_ROOT)
    tg_cfg = cfg_data.get("telegram", {})
    configured = bool(token) or bool(tg_cfg.get("token")) or bool(tg_cfg.get("enabled"))

    is_running = False
    with _telegram_lock:
        if _telegram_thread and _telegram_thread.is_alive() and _telegram_listener and not getattr(_telegram_listener, "stop_event", threading.Event()).is_set():
            is_running = True

    masked_token = None
    if token:
        masked_token = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"

    return {
        "ok": True,
        "configured": configured,
        "running": is_running,
        "token_set": bool(token),
        "token_masked": masked_token,
        "poll_seconds": float(tg_cfg.get("poll_seconds", 2)),
        "allowed_chat_ids": list(tg_cfg.get("allowed_chat_ids", [])),
        "inbox": str(tg_cfg.get("inbox", "telegram_inbox")),
    }


def start_telegram_service() -> Dict[str, Any]:
    global _telegram_listener, _telegram_thread
    from telegram.bot import TelegramListener

    cfg_data = _runtime().get("cfg", {}) if "ada_runtime" in current_app.extensions else load_config(cfg_path, PROJECT_ROOT)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or cfg_data.get("telegram", {}).get("token", "").strip()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN no configurado en variables de entorno"}

    with _telegram_lock:
        if _telegram_thread and _telegram_thread.is_alive() and _telegram_listener and not _telegram_listener.stop_event.is_set():
            return {"ok": True, "message": "El bot de Telegram ya se encuentra en ejecución"}

        port = int(os.environ.get("ADA_UI_PORT", "5005"))
        _telegram_listener = TelegramListener(cfg_data, base_url=f"http://127.0.0.1:{port}")
        _telegram_thread = _telegram_listener.start()

    return {"ok": True, "message": "Bot de Telegram iniciado correctamente en segundo plano"}


def stop_telegram_service() -> Dict[str, Any]:
    global _telegram_listener, _telegram_thread
    with _telegram_lock:
        if _telegram_listener:
            _telegram_listener.stop()
            _telegram_listener = None
            _telegram_thread = None
    return {"ok": True, "message": "Bot de Telegram detenido"}


def restart_telegram_service() -> Dict[str, Any]:
    stop_telegram_service()
    time.sleep(0.5)
    return start_telegram_service()


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


@app.route("/api/telegram/test", methods=["POST"])
def telegram_test_api():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return jsonify({"ok": False, "error": "TELEGRAM_BOT_TOKEN no configurado"}), 400
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url, headers={"User-Agent": "ADA-Hub"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return jsonify({"ok": True, "bot": data.get("result")})
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
        return jsonify({"ok": True, "config": candidate})
    safe_config = dict(runtime.get("cfg", {}))
    # sanitize sensitive paths / keys if needed
    return jsonify({"config": safe_config})


@app.route("/api/warmup", methods=["POST"])
def warmup():
    return jsonify({"runtime": _runtime()["agent"].model_manager.runtime_status(), "ok": True})


@app.route("/api/models/reload", methods=["POST"])
def reload_models():
    """Apply a validated model policy without rebuilding the running agent."""
    runtime = _runtime()
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
            return jsonify({"ok": True, "messages": []})
        return jsonify({"messages": list(state.conversation), "count": len(state.conversation)})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    runtime = _runtime()
    state = _session_state()
    with state.lock:
        payload, status_code = runtime["web_chat"].handle(data.get("message", ""), state, data.get("lang"))
    return jsonify(payload), status_code


def _sse(event, payload):
    """Encode one chat progress event for the web client."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _run_chat_in_worker(data, session_id, runtime_app):
    """Run the existing JSON chat action in an isolated request context."""
    with runtime_app.test_request_context(
        "/api/chat", method="POST", json=data, headers={"Cookie": f"ada_session={session_id}"}
    ):
        response = chat()
        if isinstance(response, tuple):
            resp_obj = response[0]
        else:
            resp_obj = response
        if hasattr(resp_obj, "get_json"):
            return resp_obj.get_json(silent=True) or {}
        if isinstance(resp_obj, dict):
            return resp_obj
        return {}


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Answer through SSE so the UI can show ADA's progress incrementally."""
    data = request.get_json() or {}
    text = data.get("message", "")
    if not text:
        return jsonify({"error": "empty message"}), 400
    state = _session_state()

    @stream_with_context
    def events():
        received = tr("status_received", data.get("lang"))
        state.conversation.extend([{"role": "assistant", "text": received, "kind": "status"}])
        yield _sse("status", {"text": received})

        processing = tr("processing", data.get("lang"))
        state.conversation.extend([{"role": "assistant", "text": processing, "kind": "status"}])
        yield _sse("status", {"text": processing})
        future = _runtime()["chat_executor"].submit(
            _run_chat_in_worker,
            data,
            state.session_id,
            current_app._get_current_object(),  # type: ignore[attr-defined]
        )
        try:
            last_update = time.monotonic()
            while not future.done():
                if time.monotonic() - last_update >= 5:
                    update = tr("status_progress", data.get("lang"))
                    state.conversation.extend([{"role": "assistant", "text": update, "kind": "status"}])
                    yield _sse("status", {"text": update})
                    last_update = time.monotonic()
                time.sleep(0.25)
            payload = future.result()
            if payload.get("error"):
                yield _sse("error", {"text": payload.get("message") or payload["error"]})
            else:
                yield _sse("reply", {"text": payload.get("reply", "(sin respuesta)")})
        except Exception as error:
            current_app.logger.exception("Streaming chat failed")
            failure = f"La tarea terminó con un error: {error}"
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
    runtime_agent = agent_instance or Agent(runtime_cfg)
    runtime_app = Flask(__name__, static_folder=str(DASHBOARD_DIR), static_url_path="/static")
    ollama_cli = OllamaClient(runtime_cfg.get("ollama_url", "http://127.0.0.1:11434"))
    mcp_mgr = MCPManager(runtime_cfg)
    runtime_app.extensions["ada_runtime"] = {
        "cfg": runtime_cfg,
        "agent": runtime_agent,
        "web_chat": WebChatService(runtime_agent, runtime_cfg),
        "session_states": {},
        "session_states_lock": threading.RLock(),
        "chat_executor": ThreadPoolExecutor(max_workers=_chat_workers(runtime_cfg), thread_name_prefix="ada-chat"),
        "ollama_client": ollama_cli,
        "model_catalog": ModelCatalog(runtime_cfg),
        "model_benchmark": ModelBenchmark(runtime_cfg.get("ollama_url", "http://127.0.0.1:11434")),
        "mcp_manager": mcp_mgr,
        "doctor": HealthDoctor(runtime_agent, runtime_cfg, mcp_mgr, ollama_cli),
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
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
