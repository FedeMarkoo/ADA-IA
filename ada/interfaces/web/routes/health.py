"""Healthcheck, diagnostics and auto-healing routes for ADA web interface."""

from __future__ import annotations

import logging
import re
import secrets
import threading
import time
from typing import Any, Dict, List
from flask import Blueprint, jsonify, request

from ada.application.services.healthcheck import (
    HealthcheckStore,
    evaluate as evaluate_healthcheck,
    functional_category,
    llm_judge,
    requires_mcp,
)
from ada.interfaces.web.doctor import HealthDoctor
from ada.interfaces.web.state import (
    WebSessionState,
    get_runtime,
)
from ada.mcps.manager import MCPManager
from ada.ollama.client import OllamaClient

logger = logging.getLogger("ada.web.health")
health_bp = Blueprint("health", __name__)


@health_bp.route("/api/healthcheck")
def healthcheck_api():
    runtime = get_runtime()
    doctor = runtime.get("doctor") or HealthDoctor(
        runtime.get("agent"),
        runtime.get("cfg"),
        runtime.get("mcp_manager") or MCPManager(),
        runtime.get("ollama_client") or OllamaClient(),
    )
    return jsonify(doctor.diagnose())


@health_bp.route("/api/healthcheck/heal", methods=["POST"])
def healthcheck_heal_api():
    runtime = get_runtime()
    doctor = runtime.get("doctor") or HealthDoctor(
        runtime.get("agent"),
        runtime.get("cfg"),
        runtime.get("mcp_manager") or MCPManager(),
        runtime.get("ollama_client") or OllamaClient(),
    )
    return jsonify(doctor.auto_heal_all())


@health_bp.route("/api/healthcheck/fix/<action_id>", methods=["POST"])
def healthcheck_fix_api(action_id):
    runtime = get_runtime()
    doctor = runtime.get("doctor") or HealthDoctor(
        runtime.get("agent"),
        runtime.get("cfg"),
        runtime.get("mcp_manager") or MCPManager(),
        runtime.get("ollama_client") or OllamaClient(),
    )
    return jsonify(doctor.fix_action(action_id))


@health_bp.route("/api/healthcheck/prompts", methods=["GET"])
def healthcheck_prompts_api():
    """Return the functional checklist stored in ADA's SQLite database."""
    store = HealthcheckStore(get_runtime()["agent"].mem)
    prompts = store.prompts()
    groups: Dict[str, List[Any]] = {}
    for item in prompts:
        groups.setdefault(item.get("functional_category") or functional_category(item.get("category")), []).append(item)
    return jsonify({"ok": True, "prompts": prompts, "groups": groups, "storage": "sqlite"})


@health_bp.route("/api/healthcheck/prompts", methods=["POST"])
def healthcheck_prompt_create_api():
    """Add a read-only case without changing application code."""
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "")
    if re.search(
        r"\b(borr|elimin|mov|renombr|escrib|creá|crea|env[ií]a|ejecut)\w*\b|\b(compra|vende)\s+(acciones?|cripto|d[oó]lares?)",
        prompt,
        re.I,
    ):
        return (
            jsonify(
                {
                    "error": "healthcheck_must_be_readonly",
                    "message": "Los casos del healthcheck solo pueden consultar o analizar.",
                }
            ),
            400,
        )
    try:
        store = HealthcheckStore(get_runtime()["agent"].mem)
        store.add_prompt({**data, "prompt": prompt})
    except ValueError as exc:
        return jsonify({"error": "invalid_healthcheck_prompt", "message": str(exc)}), 400
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            return jsonify({"error": "healthcheck_prompt_exists", "message": "Ya existe un caso con ese id."}), 409
        raise
    return jsonify({"ok": True, "id": data.get("id")}), 201


@health_bp.route("/api/healthcheck/history", methods=["GET"])
def healthcheck_history_api():
    store = HealthcheckStore(get_runtime()["agent"].mem)
    return jsonify({"ok": True, "runs": store.history()})


def _execute_healthcheck_batch(runtime: Dict[str, Any], prompts: List[Dict[str, Any]], run_id: str) -> None:
    """Run a persisted batch outside the HTTP request so reloads do not lose progress."""
    store = HealthcheckStore(runtime["agent"].mem)
    case_timeout = max(30.0, float((runtime.get("cfg") or {}).get("healthcheck_case_timeout_seconds", 300)))
    for item in prompts:
        store.mark_batch_running(run_id, item["id"])
        started = time.monotonic()
        session_id = f"{run_id}_{item['id']}"
        state = WebSessionState(runtime["agent"].mem, session_id)
        trace: List[Dict[str, Any]] = []
        executed_mcps: List[Dict[str, Any]] = []

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

        outcome: Dict[str, Any] = {}

        def runner():
            try:
                reply, _ = runtime["web_chat"].handle_message(
                    item["prompt"],
                    state,
                    progress_callback=progress,
                    session_id=session_id,
                )
                outcome["reply"] = reply
            except Exception as error:
                outcome["error"] = str(error)

        thread = threading.Thread(target=runner, name=f"hc-{item['id']}", daemon=True)
        thread.start()
        thread.join(timeout=case_timeout)
        duration = round(time.monotonic() - started, 3)

        if thread.is_alive():
            result = {
                "ok": False,
                "reason": "case_timeout",
                "message": f"El caso superó el límite de {case_timeout}s.",
                "duration_seconds": duration,
                "executed_mcps": executed_mcps,
                "trace": trace,
            }
        elif outcome.get("error"):
            result = {
                "ok": False,
                "reason": "execution_error",
                "error": outcome["error"],
                "duration_seconds": duration,
                "executed_mcps": executed_mcps,
                "trace": trace,
            }
        else:
            reply = outcome.get("reply", "")
            eval_result = evaluate_healthcheck(item, reply, duration_seconds=duration, executed_mcps=executed_mcps)
            if (
                not eval_result.get("ok")
                and str(item.get("category", "")).startswith("mcp_")
                and requires_mcp(item.get("prompt", ""))
            ):
                eval_result["reason"] = "mcp_not_used"
            judge_explanation = None
            if not eval_result.get("ok") and (runtime.get("cfg") or {}).get("healthcheck_llm_judge"):
                judge_explanation = llm_judge(runtime["agent"], item, reply)
            result = {
                **eval_result,
                "response": reply,
                "duration_seconds": duration,
                "executed_mcps": executed_mcps,
                "trace": trace,
                "judge_explanation": judge_explanation,
            }

        store.record_batch_item(run_id, item["id"], result)
    store.mark_batch_finished(run_id)


@health_bp.route("/api/healthcheck/run", methods=["POST"])
def healthcheck_run_api():
    """Start an asynchronous functional checklist batch in the background."""
    runtime = get_runtime()
    data = request.get_json(silent=True) or {}
    store = HealthcheckStore(runtime["agent"].mem)
    all_prompts = store.prompts()
    run_id = f"healthcheck_{int(time.time())}_{secrets.token_hex(4)}"

    requested_category = data.get("category")
    requested_ids = set(data.get("prompt_ids") or [])
    if requested_ids:
        prompts = [p for p in all_prompts if p["id"] in requested_ids]
    elif requested_category:
        prompts = [
            p
            for p in all_prompts
            if (p.get("functional_category") or functional_category(p.get("category"))) == requested_category
            or p.get("category") == requested_category
        ]
    else:
        prompts = all_prompts

    if not prompts:
        return (
            jsonify({"error": "no_prompts_matched", "message": "No se encontraron casos de prueba para ejecutar."}),
            400,
        )

    batch = store.create_batch(run_id, prompts, metadata={"category": requested_category})
    runtime["healthcheck_executor"].submit(_execute_healthcheck_batch, runtime, prompts, run_id)
    return jsonify({"ok": True, "run_id": run_id, "batch": batch}), 202


@health_bp.route("/api/healthcheck/runs/<run_id>")
def healthcheck_run_status_api(run_id):
    store = HealthcheckStore(get_runtime()["agent"].mem)
    batch = store.batch(run_id)
    if not batch:
        return jsonify({"error": "batch_not_found"}), 404
    return jsonify({"ok": True, "batch": batch})


@health_bp.route("/api/healthcheck/runs/<run_id>/progress")
def healthcheck_run_progress_api(run_id):
    store = HealthcheckStore(get_runtime()["agent"].mem)
    progress = store.progress(run_id)
    if not progress:
        return jsonify({"error": "batch_not_found"}), 404
    return jsonify({"ok": True, **progress})


@health_bp.route("/api/healthcheck/runs/<run_id>/cancel", methods=["POST"])
def healthcheck_run_cancel_api(run_id):
    store = HealthcheckStore(get_runtime()["agent"].mem)
    cancelled = store.cancel_batch(run_id)
    return jsonify({"ok": cancelled})


@health_bp.route("/api/healthcheck/runs/<run_id>/report")
def healthcheck_run_report_api(run_id):
    store = HealthcheckStore(get_runtime()["agent"].mem)
    batch = store.batch(run_id)
    if not batch:
        return jsonify({"error": "batch_not_found"}), 404
    return jsonify({"ok": True, "report": store.report(run_id), "batch": batch})


@health_bp.route("/api/healthcheck/runs/<run_id>/rerun-failed", methods=["POST"])
def healthcheck_run_rerun_failed_api(run_id):
    runtime = get_runtime()
    store = HealthcheckStore(runtime["agent"].mem)
    failed_prompts = store.failed_prompts_for_run(run_id)
    if not failed_prompts:
        return jsonify({"error": "no_failed_prompts", "message": "Esta corrida no tuvo casos fallidos."}), 400
    new_run_id = f"healthcheck_{int(time.time())}_{secrets.token_hex(4)}"
    batch = store.create_batch(new_run_id, failed_prompts, metadata={"rerun_from": run_id})
    runtime["healthcheck_executor"].submit(_execute_healthcheck_batch, runtime, failed_prompts, new_run_id)
    return jsonify({"ok": True, "run_id": new_run_id, "batch": batch}), 202
