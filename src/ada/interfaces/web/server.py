from flask import Flask, current_app, request, jsonify, send_from_directory, Response, stream_with_context, g
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

from ada.application.agent import Agent
from ada.application.services.web_chat import WebChatService
from ada.config import load_config, validate_config
from ada.infrastructure.runtime.resources import hardware_profile
from ada.interfaces.telegram import TelegramListener
from ada.interfaces.i18n import tr
import re
import secrets
import threading

PROJECT_ROOT = Path(__file__).resolve().parents[4]
app = Flask(__name__, static_folder=str(PROJECT_ROOT / "ui"))


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


@app.route("/")
def index():
    response = send_from_directory(str(PROJECT_ROOT / "ui"), "index.html")
    response.set_cookie("ada_csrf", _csrf_token(), samesite="Strict", secure=False)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/api/status")
def status():
    """Return active engines, local runtime health, and agent registry."""
    runtime = _runtime()
    active_agent = runtime["agent"]
    return jsonify(
        {
            "engines": active_agent.model_manager.available(),
            "runtime": active_agent.model_manager.runtime_status(),
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


@app.route("/api/audit")
def audit_api():
    limit = min(200, max(1, request.args.get("limit", default=50, type=int)))
    entries = _runtime()["agent"].mem.recent_audit(limit)
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/api/warmup", methods=["POST"])
def warmup():
    return jsonify({"runtime": _runtime()["agent"].model_manager.runtime_status(), "ok": True})


@app.route("/api/models/reload", methods=["POST"])
def reload_models():
    """Apply a validated model policy without rebuilding the running agent."""
    runtime = _runtime()
    payload = request.get_json(silent=True) or {}
    candidate = payload.get("config")
    if not isinstance(candidate, dict):
        candidate = load_config(cfg_path, PROJECT_ROOT)
    else:
        candidate = dict(candidate)
    validate_config(candidate)
    active_agent = runtime["agent"]
    previous = dict(getattr(active_agent, "cfg", {}))
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
        return response.get_json(silent=True) or {}


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Answer through SSE so the UI can show ADA's progress incrementally.

    The existing JSON endpoint remains available for Telegram and integrations.
    This endpoint deliberately reuses the same chat action, so web and Telegram
    cannot drift into different agent behavior.
    """
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
    """Create an isolated Flask application with injectable ADA dependencies.

    The module-level ``app`` remains available for the existing CLI and WSGI
    entry point. Tests, workers and embedders can use this factory to avoid
    sharing its agent and session state.
    """
    runtime_cfg = dict(config) if isinstance(config, dict) else load_config(cfg_path, PROJECT_ROOT)
    runtime_agent = agent_instance or Agent(runtime_cfg)
    runtime_app = Flask(__name__, static_folder=str(PROJECT_ROOT / "ui"))
    runtime_app.extensions["ada_runtime"] = {
        "cfg": runtime_cfg,
        "agent": runtime_agent,
        "web_chat": WebChatService(runtime_agent, runtime_cfg),
        "session_states": {},
        "session_states_lock": threading.RLock(),
        "chat_executor": ThreadPoolExecutor(max_workers=_chat_workers(runtime_cfg), thread_name_prefix="ada-chat"),
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
    telegram = TelegramListener(cfg, base_url=f"http://127.0.0.1:{port}")
    telegram.start()
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
