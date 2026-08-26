"""Core base and telemetry routes for ADA web interface."""

from __future__ import annotations

import os
import time
from flask import Blueprint, Response, jsonify, request, send_from_directory

from ada.infrastructure.prometheus_metrics import exposition
from ada.infrastructure.runtime.duplicates import detect_duplicates
from ada.infrastructure.runtime.resources import hardware_profile
from ada.interfaces.web.state import (
    ADA_VERSION,
    DASHBOARD_DIR,
    PROCESS_STARTED_AT,
    activity_snapshot,
    get_runtime,
    get_telegram_service_status,
)
from ada.mcps.manager import MCPManager
from ada.ollama.client import OllamaClient

core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def index():
    response = send_from_directory(str(DASHBOARD_DIR), "index.html")
    csrf_token = request.cookies.get("ada_csrf")
    if csrf_token:
        response.set_cookie("ada_csrf", csrf_token, samesite="Strict", secure=False)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@core_bp.route("/favicon.ico")
def favicon():
    return Response(status=204)


@core_bp.route("/api/health")
def health():
    return jsonify({"status": "healthy", "version": ADA_VERSION, "timestamp": time.time()})


@core_bp.route("/api/status")
def status():
    """Return active engines, local runtime health, and agent registry."""
    runtime = get_runtime()
    active_agent = runtime["agent"]
    ollama = runtime.get("ollama_client") or OllamaClient()
    ollama_health = ollama.health()

    if ollama_health.get("online"):
        runtime_info = active_agent.model_manager.runtime_status()
        engines = active_agent.model_manager.available()
        models = active_agent.model_manager.model_catalog()
        recommendations = active_agent.model_manager.model_recommendations()
    else:
        runtime_info = {
            "provider": "ollama",
            "endpoint": ollama.endpoint,
            "available": False,
            "reason": "ollama_offline",
        }
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
            "identity": runtime.get(
                "identity",
                {
                    "version": ADA_VERSION,
                    "started_at": PROCESS_STARTED_AT,
                    "reloaded_at": None,
                    "hot_reload": False,
                    "pid": os.getpid(),
                },
            ),
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
            "duplicates": detect_duplicates(),
        }
    )


@core_bp.route("/api/core/state")
def core_state_api():
    """Return the live topology and current execution phase for the core view."""
    runtime = get_runtime()
    summary = runtime["agent"].model_manager.selection_summary()
    return jsonify(
        {
            "activity": activity_snapshot(runtime),
            "models": {"mode": summary.get("mode", "manual"), "active": summary.get("active", {})},
            "connectors": {
                "telegram": get_telegram_service_status(),
                "mcps": runtime.get("mcp_manager", MCPManager()).list_servers(),
                "triggers": runtime.get("trigger_manager").list_triggers() if runtime.get("trigger_manager") else [],
            },
            "telemetry": {"source": "prometheus", "dashboard": "grafana"},
            "server_time": time.time(),
        }
    )


@core_bp.route("/metrics")
def prometheus_metrics():
    """Prometheus scrape endpoint. Grafana reads the Prometheus server."""
    return Response(exposition(), mimetype="text/plain; version=0.0.4")
