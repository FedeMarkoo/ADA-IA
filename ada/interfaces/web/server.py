"""Modular Flask application server and factory for ADA."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, g, jsonify, request

from ada.application.agent import Agent
from ada.application.services.memory_refiner import MemoryRefiner
from ada.application.services.web_chat import WebChatService
from ada.config import load_config
from ada.infrastructure.persistence.debug_log import DebugLog
from ada.infrastructure.prometheus_metrics import REQUESTS, REQUEST_LATENCY
from ada.infrastructure.runtime.triggers import TriggerManager
from ada.interfaces.web.routes import register_blueprints
from ada.interfaces.web.state import (
    ADA_VERSION,
    DASHBOARD_DIR,
    DEPLOYED_COMMIT,
    PROJECT_ROOT,
    PROCESS_STARTED_AT,
    WebSessionState,
    new_activity_state,
)
from ada.mcps.manager import MCPManager
from ada.models.benchmark import ModelBenchmark
from ada.models.catalog import ModelCatalog
from ada.ollama.client import OllamaClient

logger = logging.getLogger("ada.web.server")


def _chat_workers(config: Dict[str, Any]) -> int:
    configured = config.get("chat_workers")
    if configured is not None:
        return max(1, min(32, int(configured)))
    return max(2, min(8, os.cpu_count() or 2))


def _csrf_token() -> str:
    return request.cookies.get("ada_csrf") or secrets.token_urlsafe(32)


def create_app(
    config: Optional[Dict[str, Any]] = None,
    agent_instance: Optional[Agent] = None,
    config_path: Optional[Path | str] = None,
    mcp_manager: Optional[MCPManager] = None,
) -> Flask:
    """Create and configure a Flask application instance for ADA."""
    app = Flask(__name__, static_folder=str(DASHBOARD_DIR), static_url_path="/static")

    root = PROJECT_ROOT
    cfg_file = (
        Path(config_path).resolve()
        if config_path
        else (root / "ada" / "config.json" if (root / "ada" / "config.json").exists() else root / "config.json")
    )
    cfg = dict(config) if config is not None else load_config(cfg_file, root)

    mcps = mcp_manager or MCPManager(cfg)
    active_agent = agent_instance or Agent(cfg, mcp_manager=mcps)
    web_chat_svc = WebChatService(active_agent, cfg, mcp_manager=mcps)
    ollama_cli = OllamaClient(cfg.get("ollama_url", "http://127.0.0.1:11434"))
    model_cat = ModelCatalog(cfg)
    model_bm = ModelBenchmark(cfg.get("ollama_url", "http://127.0.0.1:11434"))
    trigger_mgr = TriggerManager(
        cfg,
        root,
        config_path=cfg_file,
        internal_url=f"http://127.0.0.1:{int(os.environ.get('ADA_UI_PORT', '5005'))}",
    )
    mem_refiner = MemoryRefiner(active_agent.mem, agent=active_agent, config=cfg)
    if mem_refiner.enabled:
        mem_refiner.start()

    session_states: Dict[str, WebSessionState] = {}
    session_states_lock = threading.RLock()
    chat_executor = ThreadPoolExecutor(max_workers=_chat_workers(cfg), thread_name_prefix="ada-chat")
    healthcheck_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ada-healthcheck")

    app.extensions["ada_runtime"] = {
        "cfg": cfg,
        "config_path": cfg_file,
        "agent": active_agent,
        "web_chat": web_chat_svc,
        "session_states": session_states,
        "session_states_lock": session_states_lock,
        "session_max_count": max(1, int(cfg.get("session_max_count", 256))),
        "session_ttl_seconds": max(60, int(cfg.get("session_ttl_seconds", 3600))),
        "session_history_limit": max(1, int(cfg.get("session_history_limit", 1000))),
        "chat_executor": chat_executor,
        "healthcheck_executor": healthcheck_executor,
        "ollama_client": ollama_cli,
        "model_catalog": model_cat,
        "model_benchmark": model_bm,
        "mcp_manager": mcps,
        "trigger_manager": trigger_mgr,
        "memory_refiner": mem_refiner,
        "identity": {
            "version": ADA_VERSION,
            "deployed_commit": DEPLOYED_COMMIT,
            "started_at": PROCESS_STARTED_AT,
            "reloaded_at": None,
            "hot_reload": False,
            "pid": os.getpid(),
        },
        "agent_enabled": True,
        "debug_enabled": False,
        "debug_log": DebugLog(cfg.get("debug_log_path", str(Path.home() / "Desktop/ADA_Data/debug-log.db"))),
        "activity": new_activity_state(),
        "activity_lock": threading.RLock(),
    }

    # Middlewares
    @app.before_request
    def start_prometheus_request_timer():
        g.prometheus_request_started = time.perf_counter()

    @app.after_request
    def record_prometheus_request(response):
        started = getattr(g, "prometheus_request_started", None)
        if started is not None and request.path != "/metrics":
            route = request.url_rule.rule if request.url_rule else request.path
            REQUESTS.labels(request.method, route, str(response.status_code)).inc()
            REQUEST_LATENCY.labels(request.method, route).observe(time.perf_counter() - started)
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            return jsonify({"error": error.name.lower().replace(" ", "_"), "message": error.description}), error.code

        app.logger.exception("Unhandled ADA request error: %s", error)
        correlation_id = secrets.token_hex(8)
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

    @app.before_request
    def protect_mutating_requests():
        if request.method not in {"POST", "DELETE", "PUT", "PATCH"}:
            return None
        if request.path == "/api/events":
            if (request.content_type or "").split(";", 1)[0].lower() != "application/json":
                return jsonify({"error": "content_type_must_be_json"}), 415
            expected = os.environ.get("ADA_EVENT_TOKEN") or app.extensions["ada_runtime"]["cfg"].get("event_token")
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

    @app.after_request
    def set_session_cookie(response):
        session_id = getattr(g, "ada_session_id", None)
        if session_id and not request.cookies.get("ada_session"):
            response.set_cookie("ada_session", session_id, samesite="Strict", secure=False, httponly=True)
        if not request.cookies.get("ada_csrf"):
            response.set_cookie("ada_csrf", _csrf_token(), samesite="Strict", secure=False)
        return response

    # Register all modular route blueprints
    register_blueprints(app)

    # Auto-start Prometheus in background if available
    def _auto_start_monitoring():
        try:
            time.sleep(1.0)
            from ada.infrastructure.runtime.monitoring import start_prometheus
            start_prometheus()
        except Exception:
            pass

    threading.Thread(target=_auto_start_monitoring, daemon=True, name="ada-auto-monitoring").start()

    import atexit

    def _auto_stop_services():
        try:
            from ada.interfaces.web.state import stop_telegram_service
            stop_telegram_service()
        except Exception:
            pass

    atexit.register(_auto_stop_services)

    return app


# Default singleton application for direct import
app = create_app()


def main():
    """Run the local web dashboard server."""
    port = int(os.environ.get("ADA_UI_PORT", "5005"))
    host = os.environ.get("ADA_UI_HOST", "127.0.0.1")
    print(f"🚀 ADA Dashboard iniciando en http://{host}:{port}/")
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
