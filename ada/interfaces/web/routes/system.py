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


@system_bp.route("/api/audit")
def audit_api():
    limit = min(200, max(1, request.args.get("limit", default=50, type=int)))
    entries = get_runtime()["agent"].mem.recent_audit(limit)
    return jsonify({"entries": entries, "count": len(entries)})


@system_bp.route("/api/memory/stats")
def memory_stats_api():
    runtime = get_runtime()
    active_agent = runtime["agent"]
    audit_entries = active_agent.mem.recent_audit(100)
    sessions = ["main"]
    try:
        cur = active_agent.mem.conn.cursor()
        cur.execute("SELECT DISTINCT session FROM conversation_messages")
        sessions = [row[0] for row in cur.fetchall() if row[0]] or ["main"]
    except Exception:
        pass
    return jsonify(
        {
            "stats": active_agent.mem.stats(),
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
# Telegram Connector Service Endpoints
# ==============================================================================

@system_bp.route("/api/services/telegram/status")
def telegram_service_status():
    return jsonify(get_telegram_service_status())


@system_bp.route("/api/services/telegram/toggle", methods=["POST"])
def telegram_service_toggle():
    status = get_telegram_service_status()
    if status.get("running"):
        return jsonify(stop_telegram_service())
    return jsonify(start_telegram_service())


@system_bp.route("/api/services/telegram/config", methods=["POST"])
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

    cfg_data["telegram"]["enabled"] = True
    if target_cfg_path:
        Path(target_cfg_path).write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")

    runtime["cfg"]["telegram"] = dict(cfg_data["telegram"])
    if runtime.get("trigger_manager"):
        runtime["trigger_manager"].config = runtime["cfg"]

    return jsonify({"ok": True, "message": "Token cifrado con AES-256 en SecureVault (vault.db) y configuración actualizada", "status": get_telegram_service_status()})


@system_bp.route("/api/services/telegram/logs")
def telegram_service_logs():
    return jsonify({"logs": list(telegram_logs)})
