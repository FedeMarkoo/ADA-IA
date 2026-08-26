"""Models, Ollama and benchmark routes for ADA web interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Set
from flask import Blueprint, Response, jsonify, request, stream_with_context

from ada.config import validate_config
from ada.interfaces.web.state import (
    TIMEOUT_PRESETS,
    get_runtime,
    ollama_config_payload,
)
from ada.models.benchmark import ModelBenchmark
from ada.models.catalog import ModelCatalog
from ada.ollama.client import OllamaClient

models_bp = Blueprint("models", __name__)


@models_bp.route("/api/ollama/status")
def ollama_status():
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    active_agent = runtime["agent"]
    health = client.health()
    runtime_info = active_agent.model_manager.runtime_status()
    runtime_dict = dict(runtime_info)
    if isinstance(runtime_info.get("status"), dict):
        runtime_dict["available"] = runtime_info["status"].get("available", False) or health.get("online", False)
    else:
        runtime_dict["available"] = health.get("online", False)

    return jsonify(
        {
            "health": health,
            "runtime": runtime_dict,
        }
    )


@models_bp.route("/api/ollama/models")
def ollama_models():
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    return jsonify(
        {
            "models": client.list_models(),
            "running": client.running_models(),
        }
    )


@models_bp.route("/api/ollama/running")
def ollama_running():
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    return jsonify(
        {
            "running": client.running_models(),
        }
    )


@models_bp.route("/api/ollama/unload", methods=["POST"])
def ollama_unload():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    success = client.unload_model(model_name)
    return jsonify({"ok": success, "model": model_name})


@models_bp.route("/api/ollama/load", methods=["POST"])
def ollama_load():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    cfg_data = runtime.get("cfg", {})
    keep_alive = data.get("keep_alive") or cfg_data.get("ollama_keep_alive", "2m")
    success = client.load_model(model_name, keep_alive=keep_alive)
    return jsonify({"ok": success, "model": model_name})


@models_bp.route("/api/ollama/preload_all", methods=["POST"])
def ollama_preload_all():
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    active_agent = runtime.get("agent")
    cfg_data = runtime.get("cfg", {})
    keep_alive = cfg_data.get("ollama_keep_alive", "2m")

    models_to_load: Set[str] = set()
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

    if not models_to_load:
        for m in client.list_models():
            if m.get("name"):
                models_to_load.add(m["name"])

    results = {}
    for m_name in models_to_load:
        results[m_name] = client.load_model(m_name, keep_alive=keep_alive)

    return jsonify(
        {
            "ok": any(results.values()) if results else False,
            "loaded": [m for m, ok in results.items() if ok],
            "failed": [m for m, ok in results.items() if not ok],
            "running": client.running_models(),
        }
    )


@models_bp.route("/api/ollama/delete", methods=["POST", "DELETE"])
def ollama_delete():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    success = client.delete_model(model_name)
    return jsonify({"ok": success, "model": model_name})


@models_bp.route("/api/ollama/pull/stream", methods=["POST"])
def ollama_pull_stream():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = get_runtime()
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


@models_bp.route("/api/ollama/config", methods=["GET", "POST"])
def ollama_config_api():
    runtime = get_runtime()
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
        return jsonify({"ok": True, "config": ollama_config_payload(cfg_data)})

    return jsonify(ollama_config_payload(cfg_data))


@models_bp.route("/api/ollama/details")
def ollama_details():
    model_name = request.args.get("model")
    if not model_name:
        return jsonify({"error": "model_required"}), 400
    runtime = get_runtime()
    client = runtime.get("ollama_client") or OllamaClient()
    return jsonify(client.show_model(model_name))


@models_bp.route("/api/models/catalog", methods=["GET", "POST", "DELETE"])
def models_catalog_api():
    runtime = get_runtime()
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

    return jsonify(
        {
            "catalog": catalog_mgr.get_catalog(),
            "roles": catalog_mgr.get_roles(),
        }
    )


@models_bp.route("/api/models/policy", methods=["GET", "POST"])
def models_policy_api():
    runtime = get_runtime()
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
    return jsonify(
        {
            "models": cfg_data.get("models", {}),
            "model_policy": summary["policy"],
            "manual_policy": cfg_data.get("model_policy", {}),
            **summary,
        }
    )


@models_bp.route("/api/models/benchmark/prompts", methods=["GET"])
def models_benchmark_prompts_api():
    runtime = get_runtime()
    bench = runtime.get("model_benchmark") or ModelBenchmark()
    return jsonify({"ok": True, "prompts": bench.get_prompt_catalog()})


@models_bp.route("/api/models/benchmark", methods=["POST"])
def models_benchmark_api():
    data = request.get_json(silent=True) or {}
    model_name = data.get("model")
    prompt_key = data.get("prompt_key", "quick")
    custom_prompt = data.get("custom_prompt")
    run_suite = bool(data.get("run_suite") or prompt_key == "suite")
    prompt_keys = data.get("prompt_keys")

    if not model_name:
        return jsonify({"error": "model_required", "message": "Se requiere especificar un modelo"}), 400

    runtime = get_runtime()
    bench = runtime.get("model_benchmark") or ModelBenchmark()

    if run_suite:
        result = bench.run_suite(model_name, prompt_keys=prompt_keys)
    else:
        result = bench.run(model_name, prompt_key=prompt_key, custom_prompt=custom_prompt)

    return jsonify(result)


@models_bp.route("/api/models/reload", methods=["POST"])
def models_reload_api():
    runtime = get_runtime()
    payload = request.get_json(silent=True) or {}
    config_update = payload.get("config", {})
    if not isinstance(config_update, dict):
        return jsonify({"error": "invalid_payload"}), 400
    candidate = dict(runtime["cfg"])
    candidate.update(config_update)
    for protected in ("db_path", "photo_root", "inbox", "food_profile", "allowed_roots"):
        if protected in config_update and config_update[protected] != runtime["cfg"].get(protected):
            return jsonify({"error": f"No se puede mutar {protected} en caliente."}), 400
    try:
        validate_config(candidate)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "invalid_config", "message": str(exc)}), 400
    runtime["cfg"].clear()
    runtime["cfg"].update(candidate)
    active_agent = runtime["agent"]
    active_agent.model_manager.reload(candidate)
    active_agent.router.config = candidate
    active_agent.policy.config = candidate
    active_agent.cfg = candidate
    return jsonify(
        {
            "ok": True,
            "adaptive": candidate.get("adaptive_models", False),
            "models": candidate.get("models", {}),
            "status": (
                active_agent.model_manager.runtime_status()
                if hasattr(active_agent.model_manager, "runtime_status")
                else {}
            ),
        }
    )
