"""Healthcheck, diagnostics and auto-healing routes for ADA web interface."""

from __future__ import annotations

import logging
import re
import secrets
import threading
import time
from typing import Any, Dict, List
from flask import Blueprint, current_app, jsonify, request

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

_healthcheck_active_run_ids = set()
_healthcheck_active_runs_lock = threading.RLock()


def _healthcheck_active_runs():
    with _healthcheck_active_runs_lock:
        return set(_healthcheck_active_run_ids)


def _recover_orphaned_healthchecks(store):
    return store.recover_orphaned_batches(_healthcheck_active_runs())


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
            trace.append({
                "phase": "case_timeout",
                "timeout_seconds": case_timeout,
                "at_seconds": round(time.monotonic() - started, 3),
            })
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

        duration = round(time.monotonic() - started, 3)
        evaluation = evaluate_healthcheck(item, reply, duration, error)
        model = payload.get("model") if isinstance(payload, dict) else None
        for event in reversed(trace):
            if event.get("model"):
                model = event["model"]
                break

        # Every case is evaluated by the independent IA judge. Regex criteria
        # remain auxiliary signals only and are included in the judge context.
        if True:
            cfg = runtime.get("cfg") or {}
            policy = cfg.get("model_policy", {}).get("reasoning", {})
            judge_model = (
                cfg.get("healthcheck_judge_model")
                or policy.get("preferred")
                or cfg.get("models", {}).get("chat", "llama3.2:3b")
            )
            judge = llm_judge(
                item,
                reply,
                cfg.get("ollama_url", "http://127.0.0.1:11434"),
                judge_model,
                mcp_evidence=[mcp for mcp in executed_mcps if mcp.get("ok") is True],
                execution_error=error,
            )
            evaluation["judge"] = judge
            evaluation["passed"] = bool(judge.get("passed"))
            evaluation["score"] = judge.get("score", 0.0)
            evaluation["issues"] = judge.get("issues", [])
            evaluation["rationale"] = judge.get("rationale", "")
            trace.append({
                "phase": "judge_finished",
                "model": judge.get("model"),
                "source": judge.get("source"),
                "score": judge.get("score"),
                "passed": judge.get("passed"),
                "at_seconds": round(time.monotonic() - started, 3),
            })

        status_name = "passed" if evaluation["passed"] else ("error" if error else "failed")
        unique_mcps: List[Dict[str, Any]] = []
        seen_mcps = set()
        for mcp in executed_mcps:
            key = (mcp.get("server"), mcp.get("tool"))
            if key not in seen_mcps:
                seen_mcps.add(key)
                unique_mcps.append(mcp)
            else:
                existing = next(item for item in unique_mcps if (item.get("server"), item.get("tool")) == key)
                for field, value in mcp.items():
                    if value is not None:
                        existing[field] = value

        current_batch = store.batch(run_id)
        if not current_batch or current_batch["status"] != "running":
            return

        store.save_run(
            run_id,
            item["id"],
            reply,
            evaluation,
            evaluation["elapsed_seconds"],
            request=item["prompt"],
            status=status_name,
            status_code=status,
            model=model,
            mcps=unique_mcps,
            trace=trace,
        )
        store.mark_batch_item(run_id, evaluation["passed"])

    store.finish_batch(run_id)


@health_bp.route("/api/healthcheck/runs/active", methods=["GET"])
def healthcheck_active_runs_api():
    store = HealthcheckStore(get_runtime()["agent"].mem)
    _recover_orphaned_healthchecks(store)
    return jsonify({"ok": True, "runs": store.active_batches()})


@health_bp.route("/api/healthcheck/batches", methods=["GET"])
def healthcheck_batches_api():
    store = HealthcheckStore(get_runtime()["agent"].mem)
    _recover_orphaned_healthchecks(store)
    return jsonify({"ok": True, "runs": store.recent_batches()})


@health_bp.route("/api/healthcheck/latest", methods=["GET"])
def healthcheck_latest_api():
    store = HealthcheckStore(get_runtime()["agent"].mem)
    return jsonify({"ok": True, "results": store.latest_results()})


@health_bp.route("/api/healthcheck/runs/<run_id>", methods=["GET"])
def healthcheck_run_status_api(run_id):
    store = HealthcheckStore(get_runtime()["agent"].mem)
    _recover_orphaned_healthchecks(store)
    batch = store.batch(run_id)
    if not batch:
        return jsonify({"error": "healthcheck_run_not_found"}), 404
    include_history = request.args.get("details", "1").lower() not in {"0", "false", "no"}
    history = [item for item in store.history(200) if item["run_id"] == run_id] if include_history else []
    return jsonify({"ok": True, "run": batch, "batch": batch, "history": history})


@health_bp.route("/api/healthcheck/runs/<run_id>/progress")
def healthcheck_run_progress_api(run_id):
    store = HealthcheckStore(get_runtime()["agent"].mem)
    batch = store.batch(run_id)
    if not batch:
        return jsonify({"error": "batch_not_found"}), 404
    return jsonify({"ok": True, **batch})


@health_bp.route("/api/healthcheck/runs/<run_id>/cancel", methods=["POST"])
def healthcheck_run_cancel_api(run_id):
    """Mark a stalled healthcheck as interrupted without killing ADA."""
    store = HealthcheckStore(get_runtime()["agent"].mem)
    changed = store.interrupt_batch(run_id)
    with _healthcheck_active_runs_lock:
        _healthcheck_active_run_ids.discard(run_id)
    batch = store.batch(run_id)
    if not batch:
        return jsonify({"error": "healthcheck_run_not_found"}), 404
    return jsonify({"ok": True, "changed": bool(changed), "run": batch, "batch": batch})


@health_bp.route("/api/healthcheck/run", methods=["POST"])
def healthcheck_run_api():
    """Create a durable batch and execute it in the background."""
    runtime = get_runtime()
    data = request.get_json(silent=True) or {}
    store = HealthcheckStore(runtime["agent"].mem)
    all_prompts = store.prompts()

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
            jsonify({"error": "healthcheck_no_prompts", "message": "No se encontraron casos de prueba para ejecutar."}),
            400,
        )

    run_id = f"healthcheck_{int(time.time())}_{secrets.token_hex(4)}"
    store.begin_batch(run_id, [item["id"] for item in prompts])
    with _healthcheck_active_runs_lock:
        _healthcheck_active_run_ids.add(run_id)

    try:
        executor = runtime.get("healthcheck_executor")
        future = executor.submit(_execute_healthcheck_batch, runtime, prompts, run_id)

        def healthcheck_done(done_future):
            with _healthcheck_active_runs_lock:
                _healthcheck_active_run_ids.discard(run_id)
            try:
                done_future.result()
            except Exception:
                logger.exception("healthcheck_batch_failed run_id=%s", run_id)
                try:
                    HealthcheckStore(runtime["agent"].mem).interrupt_batch(run_id)
                except Exception:
                    pass

        future.add_done_callback(healthcheck_done)
    except Exception:
        with _healthcheck_active_runs_lock:
            _healthcheck_active_run_ids.discard(run_id)
        raise

    batch = store.batch(run_id)
    return jsonify({"ok": True, "accepted": True, "run_id": run_id, "run": batch, "batch": batch}), 202
