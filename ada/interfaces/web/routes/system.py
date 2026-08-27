"""System, triggers, updates, Telegram connector and audit routes for ADA web interface."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from flask import Blueprint, jsonify, request

from ada.infrastructure.update.update_manager import UpdateManager
from ada.interfaces.web.state import (
    get_runtime,
    get_telegram_service_status,
    start_telegram_service,
    stop_telegram_service,
    telegram_logs,
)
from ada.infrastructure.credentials import SecureVault

logger = logging.getLogger("ada.web.system")
system_bp = Blueprint("system", __name__)


@system_bp.route("/api/agent/restart", methods=["POST"])
def agent_restart_api():
    """Reset the in-process agent lifecycle without recreating the Flask app."""
    runtime = get_runtime()
    agent = runtime.get("agent")
    if not agent:
        return jsonify({"ok": False, "error": "agent_not_available"}), 500
    agent.running = True
    runtime["agent_enabled"] = True
    return jsonify({"ok": True, "message": "Agente listo nuevamente."})


@system_bp.route("/api/agent/start", methods=["POST"])
def agent_start_api():
    runtime = get_runtime()
    runtime["agent_enabled"] = True
    agent = runtime.get("agent")
    if agent:
        agent.running = True
    return jsonify({"ok": True, "message": "Agente iniciado.", "agent_enabled": True})


@system_bp.route("/api/agent/stop", methods=["POST"])
def agent_stop_api():
    runtime = get_runtime()
    runtime["agent_enabled"] = False
    return jsonify({"ok": True, "message": "Agente detenido.", "agent_enabled": False})


@system_bp.route("/api/mcps/servers")
def mcp_servers_api():
    manager = get_runtime().get("mcp_manager")
    return jsonify({"servers": manager.list_servers() if manager else []})


@system_bp.route("/api/mcps/tools")
def mcp_tools_api():
    manager = get_runtime().get("mcp_manager")
    return jsonify({"tools": manager.list_tools() if manager else []})


@system_bp.route("/api/mcps/servers/<name>/<action>", methods=["POST", "GET"])
def mcp_server_action_api(name, action):
    manager = get_runtime().get("mcp_manager")
    if not manager:
        return jsonify({"ok": False, "error": "mcp_manager_not_available"}), 500
    handlers = {
        "start": manager.start_server,
        "stop": manager.stop_server,
        "restart": manager.restart_server,
        "ping": manager.ping_server,
    }
    handler = handlers.get(action)
    if not handler:
        return jsonify({"ok": False, "error": "unknown_mcp_action"}), 404
    result = handler(name)
    return jsonify(result), 200 if result.get("ok") else 404


@system_bp.route("/api/mcps/servers/restart-all", methods=["POST"])
def mcp_restart_all_api():
    manager = get_runtime().get("mcp_manager")
    if not manager:
        return jsonify({"ok": False, "error": "mcp_manager_not_available"}), 500
    return jsonify(manager.restart_all_servers())


@system_bp.route("/api/audit")
def audit_api():
    limit = min(200, max(1, request.args.get("limit", default=50, type=int)))
    entries = get_runtime()["agent"].operations.recent_audit(limit)
    return jsonify({"entries": entries, "count": len(entries)})


@system_bp.route("/api/memory/stats")
def memory_stats_api():
    runtime = get_runtime()
    active_agent = runtime["agent"]
    audit_entries = active_agent.operations.recent_audit(100)
    sessions = ["main"]
    try:
        cur = active_agent.mem.conn.cursor()
        cur.execute("SELECT DISTINCT session FROM conversation_messages")
        sessions = [row[0] for row in cur.fetchall() if row[0]] or ["main"]
    except Exception:
        pass
    return jsonify(
        {
            **active_agent.mem.stats(),
            "operations": active_agent.operations.stats(),
            "stats": {**active_agent.mem.stats(), **active_agent.operations.stats()},
            "procedures": active_agent.mem.list_procedures(),
            "recent_audit": audit_entries,
            "sessions": sessions,
        }
    )


@system_bp.route("/api/memory/refiner/run", methods=["POST"])
def memory_refiner_run_api():
    runtime = get_runtime()
    refiner = runtime.get("memory_refiner")
    if not refiner:
        return jsonify({"ok": False, "error": "refiner_not_available"}), 400
    try:
        report = refiner.refine_cycle()
        return jsonify({"ok": True, "report": report})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@system_bp.route("/api/events", methods=["POST"])
def receive_event():
    """Event ingress endpoint for external triggers (filesystem, webhooks, mobile)."""
    import secrets

    runtime = get_runtime()
    payload = request.get_json(silent=True) or {}
    topic = payload.get("topic") or payload.get("event")
    event_payload = payload.get("payload") if "payload" in payload else payload.get("data", {})
    if not topic:
        return jsonify({"error": "topic_required"}), 400

    event_id = secrets.token_hex(8)
    active_agent = runtime.get("agent")
    if active_agent and hasattr(active_agent, "mem") and hasattr(active_agent.mem, "record_event"):
        active_agent.mem.record_event(topic, event_payload, event_id=event_id)

    trigger_mgr = runtime.get("trigger_manager")
    if trigger_mgr:
        try:
            trigger_mgr.dispatch_event(topic, event_payload)
        except Exception:
            pass

    return jsonify({"ok": True, "event_id": event_id, "topic": topic}), 202


@system_bp.route("/api/triggers")
def triggers_api():
    runtime = get_runtime()
    trigger_mgr = runtime.get("trigger_manager")
    if not trigger_mgr:
        return jsonify({"triggers": []})
    return jsonify({"triggers": trigger_mgr.list_triggers()})


@system_bp.route("/api/triggers/<trigger_name>/toggle", methods=["POST"])
def trigger_toggle_api(trigger_name):
    runtime = get_runtime()
    trigger_mgr = runtime.get("trigger_manager")
    if not trigger_mgr:
        return jsonify({"error": "trigger_manager_not_available"}), 500
    payload = request.get_json(silent=True) or {}
    enable = payload.get("enable", True)
    result = trigger_mgr.toggle_trigger(trigger_name, enable=enable)
    return jsonify(result)


@system_bp.route("/api/triggers/<trigger_name>/status")
def trigger_status_api(trigger_name):
    runtime = get_runtime()
    trigger_mgr = runtime.get("trigger_manager")
    if not trigger_mgr:
        return jsonify({"error": "trigger_manager_not_available"}), 500
    return jsonify(trigger_mgr.get_trigger_status(trigger_name))


@system_bp.route("/api/presence", methods=["GET", "POST"])
def presence_api():
    runtime = get_runtime()
    trigger_mgr = runtime.get("trigger_manager")
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        location = payload.get("location", "home")
        device = payload.get("device", "manual")
        if trigger_mgr:
            trigger_mgr.update_presence(location, device=device)
        return jsonify({"ok": True, "location": location, "device": device})
    if trigger_mgr:
        return jsonify(trigger_mgr.get_presence())
    return jsonify({"location": "unknown", "updated_at": None})


@system_bp.route("/api/presence/status")
def presence_status_api():
    runtime = get_runtime()
    trigger_mgr = runtime.get("trigger_manager")
    if trigger_mgr:
        return jsonify(trigger_mgr.get_presence())
    return jsonify({"location": "unknown"})


@system_bp.route("/api/presence/history")
def presence_history_api():
    runtime = get_runtime()
    trigger_mgr = runtime.get("trigger_manager")
    if trigger_mgr:
        return jsonify({"history": trigger_mgr.get_presence_history()})
    return jsonify({"history": []})


@system_bp.route("/api/update/status")
def update_status_api():
    runtime = get_runtime()
    updater = UpdateManager(runtime.get("cfg", {}))
    return jsonify(updater.get_status())


@system_bp.route("/api/update/check", methods=["POST"])
def update_check_api():
    runtime = get_runtime()
    updater = UpdateManager(runtime.get("cfg", {}))
    return jsonify(updater.check_for_updates())


@system_bp.route("/api/update/apply", methods=["POST"])
def update_apply_api():
    runtime = get_runtime()
    updater = UpdateManager(runtime.get("cfg", {}))
    return jsonify(updater.apply_update())


# ==============================================================================
# ==============================================================================
# Telegram Connector Service Endpoints
# ==============================================================================


@system_bp.route("/api/services/telegram/status")
@system_bp.route("/api/telegram/status")
def telegram_service_status():
    return jsonify(get_telegram_service_status())


@system_bp.route("/api/services/telegram/toggle", methods=["POST"])
def telegram_service_toggle():
    status = get_telegram_service_status()
    if status.get("running"):
        return jsonify(stop_telegram_service())
    return jsonify(start_telegram_service())


@system_bp.route("/api/telegram/start", methods=["POST"])
def telegram_start_api():
    return jsonify(start_telegram_service())


@system_bp.route("/api/telegram/stop", methods=["POST"])
def telegram_stop_api():
    return jsonify(stop_telegram_service())


@system_bp.route("/api/telegram/restart", methods=["POST"])
def telegram_restart_api():
    from ada.interfaces.web.state import restart_telegram_service
    return jsonify(restart_telegram_service())


@system_bp.route("/api/telegram/history")
def telegram_history_api():
    runtime = get_runtime()
    messages = []
    try:
        mem = runtime["agent"].mem
        cur = mem.conn.cursor()
        cur.execute(
            "SELECT id, session, role, content, created_at FROM conversation_messages WHERE session LIKE 'tg_%' OR session LIKE 'telegram_%' ORDER BY id DESC LIMIT 50"
        )
        for row in cur.fetchall():
            messages.append(
                {
                    "id": row[0],
                    "session": row[1],
                    "role": row[2],
                    "content": row[3],
                    "created_at": str(row[4]),
                }
            )
    except Exception:
        pass
    return jsonify({"ok": True, "messages": messages})


@system_bp.route("/api/services/telegram/config", methods=["POST"])
@system_bp.route("/api/telegram/config", methods=["POST"])
def telegram_service_config():
    runtime = get_runtime()
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()
    allowed_chat_ids = body.get("allowed_chat_ids")

    if token:
        try:
            vault = SecureVault()
            vault.set("telegram_bot_token", token, meta={"service": "telegram", "updated_at": time.time()})
        except Exception as exc:
            return jsonify({"ok": False, "error": f"No se pudo guardar el token en la bóveda: {exc}"}), 500

    target_cfg_path = runtime.get("config_path")
    cfg_data = dict(runtime.get("cfg", {}))
    cfg_data.setdefault("telegram", {})

    cfg_data["telegram"].pop("token", None)
    cfg_data.pop("telegram_token", None)
    cfg_data.pop("telegram_bot_token", None)

    if allowed_chat_ids is not None:
        if isinstance(allowed_chat_ids, str):
            allowed_chat_ids = [s.strip() for s in allowed_chat_ids.split(",") if s.strip()]
        cfg_data["telegram"]["allowed_chat_ids"] = allowed_chat_ids
        try:
            vault = SecureVault()
            vault.set(
                "telegram_allowed_chat_ids",
                ",".join(str(cid) for cid in allowed_chat_ids),
                meta={"service": "telegram", "updated_at": time.time()},
            )
        except Exception as exc:
            pass

    cfg_data["telegram"]["enabled"] = True
    save_path = Path(target_cfg_path) if target_cfg_path else (PROJECT_ROOT / "ada" / "config.json")
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    runtime["cfg"]["telegram"] = dict(cfg_data["telegram"])
    if runtime.get("trigger_manager"):
        runtime["trigger_manager"].config = runtime["cfg"]

    from ada.interfaces.web.state import get_telegram_service_status, restart_telegram_service
    status = get_telegram_service_status()
    if status.get("running"):
        restart_telegram_service()

    return jsonify(
        {
            "ok": True,
            "message": "Token cifrado con AES-256 en SecureVault (vault.db) y configuración actualizada",
            "status": get_telegram_service_status(),
        }
    )


@system_bp.route("/api/services/telegram/logs")
@system_bp.route("/api/telegram/logs")
def telegram_service_logs():
    return jsonify({"logs": list(telegram_logs)})


# ==============================================================================
# Monitoring & Telemetry (Prometheus & Grafana) Endpoints
# ==============================================================================


@system_bp.route("/api/monitoring/status")
def monitoring_status_api():
    from ada.infrastructure.runtime.monitoring import get_monitoring_status
    return jsonify(get_monitoring_status())


@system_bp.route("/api/monitoring/start-all", methods=["POST"])
def monitoring_start_all_api():
    from ada.infrastructure.runtime.monitoring import start_monitoring_all
    return jsonify(start_monitoring_all())


@system_bp.route("/api/monitoring/prometheus/status")
def monitoring_prometheus_status_api():
    from ada.infrastructure.runtime.monitoring import get_prometheus_status
    return jsonify(get_prometheus_status())


@system_bp.route("/api/monitoring/prometheus/start", methods=["POST"])
def monitoring_prometheus_start_api():
    from ada.infrastructure.runtime.monitoring import start_prometheus
    return jsonify(start_prometheus())


@system_bp.route("/api/monitoring/prometheus/stop", methods=["POST"])
def monitoring_prometheus_stop_api():
    from ada.infrastructure.runtime.monitoring import stop_prometheus
    return jsonify(stop_prometheus())


@system_bp.route("/api/monitoring/prometheus/restart", methods=["POST"])
def monitoring_prometheus_restart_api():
    from ada.infrastructure.runtime.monitoring import restart_prometheus
    return jsonify(restart_prometheus())


@system_bp.route("/api/monitoring/grafana/status")
def monitoring_grafana_status_api():
    from ada.infrastructure.runtime.monitoring import get_grafana_status
    return jsonify(get_grafana_status())


@system_bp.route("/api/monitoring/grafana/start", methods=["POST"])
def monitoring_grafana_start_api():
    from ada.infrastructure.runtime.monitoring import start_grafana
    return jsonify(start_grafana())


@system_bp.route("/api/monitoring/grafana/stop", methods=["POST"])
def monitoring_grafana_stop_api():
    from ada.infrastructure.runtime.monitoring import stop_grafana
    return jsonify(stop_grafana())


@system_bp.route("/api/monitoring/grafana/restart", methods=["POST"])
def monitoring_grafana_restart_api():
    from ada.infrastructure.runtime.monitoring import restart_grafana
    return jsonify(restart_grafana())
