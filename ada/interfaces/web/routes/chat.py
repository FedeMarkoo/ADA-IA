"""Chat, streaming, pending actions and activity routes for ADA web interface."""

from __future__ import annotations

import json
import logging
import secrets
import time
from queue import Empty, Queue
from flask import Blueprint, Response, jsonify, request, stream_with_context

from ada.infrastructure.prometheus_metrics import RESPONSES, operation_finished, operation_started
from ada.interfaces.web.state import (
    activity_snapshot,
    activity_update,
    get_runtime,
    get_session_state,
)

logger = logging.getLogger("ada.web.chat")
chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/api/conversation", methods=["GET", "DELETE"])
def conversation_api():
    runtime = get_runtime()
    state = get_session_state()
    if request.method == "DELETE":
        state.conversation.clear()
        state.pending_action = None
        state.pending_path_action = None
        state.current_path = None
        if hasattr(runtime["agent"].mem, "clear_folder_context"):
            runtime["agent"].mem.clear_folder_context(state.session_id)
        return jsonify({"ok": True, "messages": []})
    return jsonify({"messages": list(state.conversation)})


@chat_bp.route("/api/action/confirm", methods=["POST"])
def confirm_action():
    state = get_session_state()
    runtime = get_runtime()
    if not state.pending_action:
        return jsonify({"error": "no_pending_action"}), 400
    pending = state.pending_action
    state.pending_action = None
    started = time.perf_counter()
    operation_started("action.confirm")
    try:
        reply = runtime["web_chat"].execute_confirmed_action(pending, state)
        operation_finished("action.confirm", started, success=True)
        return jsonify({"reply": reply, "messages": list(state.conversation)})
    except Exception as exc:
        operation_finished("action.confirm", started, success=False)
        return jsonify({"error": "action_execution_failed", "message": str(exc)}), 500


@chat_bp.route("/api/action/cancel", methods=["POST"])
def cancel_action():
    state = get_session_state()
    state.pending_action = None
    state.pending_path_action = None
    return jsonify({"ok": True, "message": "Acción cancelada."})


@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """Synchronous chat endpoint using the unified WebChatService."""
    runtime = get_runtime()
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "El mensaje no puede estar vacío."}), 400

    state = get_session_state()
    lang = payload.get("lang") or state.conversation.memory.get_preference("lang", "es")
    source = payload.get("source") or ("telegram" if request.headers.get("X-ADA-Source") == "telegram" else "web")
    request_id = secrets.token_hex(4)

    def progress(phase, details=None, **kwargs):
        data = dict(details or {})
        data.update(kwargs)
        activity_update(runtime, phase, data, session_id=state.session_id)

    activity_update(runtime, "received", {"message": message, "channel": source}, session_id=state.session_id)
    logger.info("request_received id=%s channel=%s chars=%d", request_id, source, len(message))

    res, status_code = runtime["web_chat"].handle(
        message,
        state,
        lang=lang,
        progress=progress,
    )

    RESPONSES.labels(source, str(status_code)).inc()
    return jsonify(res), status_code


@chat_bp.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Event-stream chat: receives text, yields structured execution events."""
    runtime = get_runtime()
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "El mensaje no puede estar vacío."}), 400

    state = get_session_state()
    lang = payload.get("lang") or "es"
    source = payload.get("source") or "web"
    event_queue: Queue = Queue()

    def progress(phase, details=None, **kwargs):
        data = dict(details or {})
        data.update(kwargs)
        activity_update(runtime, phase, data, session_id=state.session_id)
        event_queue.put({"type": "progress", "phase": phase, "data": details or {}})

    activity_update(runtime, "received", {"message": message, "channel": source}, session_id=state.session_id)
    event_queue.put({"type": "progress", "phase": "received", "data": {"message": message[:80]}})

    def worker():
        try:
            res, status_code = runtime["web_chat"].handle(
                message,
                state,
                lang=lang,
                progress=progress,
            )
            event_queue.put(
                {
                    "type": "result",
                    **res,
                    "session_id": state.session_id,
                    "messages": list(state.conversation)[-10:],
                }
            )
        except Exception as exc:
            activity_update(runtime, "error", {"error": str(exc)}, session_id=state.session_id)
            event_queue.put({"type": "error", "error": str(exc), "message": "Error al procesar el mensaje."})
        finally:
            event_queue.put(None)

    runtime["chat_executor"].submit(worker)

    @stream_with_context
    def generate():
        while True:
            try:
                item = event_queue.get(timeout=0.25)
            except Empty:
                yield ": keepalive\n\n"
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@chat_bp.route("/api/activity")
def activity_api():
    """Return the current activity status of ADA."""
    return jsonify(activity_snapshot(get_runtime()))


@chat_bp.route("/api/activity/stream")
def activity_stream():
    """Server-Sent Events stream for ADA activity state."""
    runtime = get_runtime()

    @stream_with_context
    def generate():
        last_state = None
        while True:
            current_state = activity_snapshot(runtime)
            payload = json.dumps(current_state, ensure_ascii=False)
            if payload != last_state:
                last_state = payload
                yield f"data: {payload}\n\n"
            else:
                yield ": keepalive\n\n"
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@chat_bp.route("/api/debug/toggle", methods=["POST"])
def debug_toggle_api():
    runtime = get_runtime()
    payload = request.get_json(silent=True) or {}
    enable = payload.get("enable")
    if enable is None:
        new_state = not runtime.get("debug_enabled", False)
    else:
        new_state = bool(enable)
    runtime["debug_enabled"] = new_state
    if runtime.get("debug_log"):
        runtime["debug_log"].set_enabled(new_state)
    return jsonify({"ok": True, "debug_enabled": new_state})


@chat_bp.route("/api/debug/events")
def debug_events_api():
    runtime = get_runtime()
    if not runtime.get("debug_log"):
        return jsonify({"ok": True, "events": []})
    limit = min(500, max(1, request.args.get("limit", default=100, type=int)))
    session_id = request.args.get("session_id")
    events = runtime["debug_log"].read(limit=limit, session_id=session_id)
    return jsonify(
        {"ok": True, "events": events, "count": len(events), "debug_enabled": runtime.get("debug_enabled", False)}
    )


@chat_bp.route("/api/debug/events/stream")
def debug_events_stream():
    runtime = get_runtime()

    @stream_with_context
    def generate():
        last_id = 0
        while True:
            if runtime.get("debug_log"):
                events = runtime["debug_log"].read_after(last_id, limit=50)
                for event in events:
                    last_id = max(last_id, event["id"])
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield ": keepalive\n\n"
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
