#!/usr/bin/env python3
"""
ADA Management Model Context Protocol (MCP) Server for Antigravity IDE.
Implements the standard MCP JSON-RPC 2.0 protocol over stdio to manage and operate
all features of ADA (Chat, Models, Ollama, MCPs, Diagnostics, Vault, Triggers, Telegram, Memory).
"""

import sys
import json
import os
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from typing import Any, Dict, Optional

ADA_API_URL = os.environ.get("ADA_API_URL", "http://127.0.0.1:5005").rstrip("/")

# Global CookieJar to persist session & CSRF tokens across requests
_cookie_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookie_jar))


def _get_csrf_token() -> Optional[str]:
    """Retrieve CSRF token from active cookies if present."""
    for cookie in _cookie_jar:
        if cookie.name == "ada_csrf":
            return cookie.value
    return None


def _ada_api(endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
    """Execute an HTTP request against the ADA Web API with automatic session and CSRF handling."""
    if params:
        query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{ADA_API_URL}{endpoint}?{query_string}"
    else:
        url = f"{ADA_API_URL}{endpoint}"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "ADA-MCP-Server/1.0")

    # Add CSRF token header if known
    csrf = _get_csrf_token()
    if csrf:
        req.add_header("X-ADA-Token", csrf)

    try:
        with _opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return {"ok": True, "status_code": resp.status}
            return json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        try:
            parsed = json.loads(err_body)
            return {"error": True, "code": e.code, "message": parsed.get("message", parsed.get("error", err_body)), "details": parsed}
        except Exception:
            return {"error": True, "code": e.code, "message": err_body}
    except urllib.error.URLError as e:
        return {
            "error": True,
            "offline": True,
            "message": f"No se pudo conectar a ADA en {ADA_API_URL}. ¿Está el servidor iniciado? ({e.reason})",
            "url": ADA_API_URL
        }
    except Exception as e:
        return {"error": True, "message": str(e)}


# =============================================================================
# Tool Handlers: 1. System Status & Identity
# =============================================================================

def handle_ada_status(args: dict) -> str:
    """Return full status of ADA: engines, ollama health, models, hardware, MCPs, metrics."""
    res = _ada_api("/api/status")
    return json.dumps(res, indent=2, default=str)


def handle_ada_core_state(args: dict) -> str:
    """Return live topology, connectors, active models, and recent activity phases."""
    res = _ada_api("/api/core/state")
    return json.dumps(res, indent=2, default=str)


def handle_ada_activity(args: dict) -> str:
    """Return current activity status and recent event phases."""
    res = _ada_api("/api/activity")
    return json.dumps(res, indent=2, default=str)


def handle_ada_restart_agent(args: dict) -> str:
    """Reset the in-process agent lifecycle without restarting the whole server."""
    res = _ada_api("/api/agent/restart", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


# =============================================================================
# Tool Handlers: 2. Chat & Conversation
# =============================================================================

def handle_ada_chat(args: dict) -> str:
    """Send a message/task to ADA and return the structured response."""
    message = args.get("message", "").strip()
    if not message:
        return json.dumps({"error": "El parámetro 'message' es requerido."})

    lang = args.get("lang", "es")
    source = args.get("source", "mcp-ide")
    timeout = float(args.get("timeout_seconds", 300))

    payload = {"message": message, "lang": lang, "source": source}
    res = _ada_api("/api/chat", method="POST", payload=payload, timeout=timeout)
    return json.dumps(res, indent=2, default=str)


def handle_ada_conversation_get(args: dict) -> str:
    """Retrieve message history for current session."""
    res = _ada_api("/api/conversation", method="GET")
    return json.dumps(res, indent=2, default=str)


def handle_ada_conversation_clear(args: dict) -> str:
    """Clear conversation history and reset folder context."""
    res = _ada_api("/api/conversation", method="DELETE")
    return json.dumps(res, indent=2, default=str)


def handle_ada_action_confirm(args: dict) -> str:
    """Confirm a pending sensitive action."""
    res = _ada_api("/api/action/confirm", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_action_cancel(args: dict) -> str:
    """Cancel a pending action."""
    res = _ada_api("/api/action/cancel", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_debug_toggle(args: dict) -> str:
    """Toggle debug event logging on or off."""
    enable = args.get("enable")
    payload = {} if enable is None else {"enable": bool(enable)}
    res = _ada_api("/api/debug/toggle", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_debug_events(args: dict) -> str:
    """Read recent debug trace events."""
    limit = args.get("limit", 50)
    session_id = args.get("session_id")
    res = _ada_api("/api/debug/events", params={"limit": limit, "session_id": session_id})
    return json.dumps(res, indent=2, default=str)


# =============================================================================
# Tool Handlers: 3. Models & Ollama Management
# =============================================================================

def handle_ada_ollama_status(args: dict) -> str:
    """Check Ollama service status, health, and local runtime."""
    res = _ada_api("/api/ollama/status")
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_list_models(args: dict) -> str:
    """List installed models and running models in Ollama."""
    res = _ada_api("/api/ollama/models")
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_load_model(args: dict) -> str:
    """Explicitly switch to and load a model into memory."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "El parámetro 'model' es requerido."})
    res = _ada_api("/api/ollama/load", method="POST", payload={"model": model})
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_unload_model(args: dict) -> str:
    """Unload a model from memory to free VRAM/RAM."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "El parámetro 'model' es requerido."})
    res = _ada_api("/api/ollama/unload", method="POST", payload={"model": model})
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_preload_all(args: dict) -> str:
    """Preload configured models into memory."""
    res = _ada_api("/api/ollama/preload_all", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_delete_model(args: dict) -> str:
    """Delete a local model from Ollama."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "El parámetro 'model' es requerido."})
    res = _ada_api("/api/ollama/delete", method="POST", payload={"model": model})
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_show_model(args: dict) -> str:
    """Show detailed model configuration and parameters."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "El parámetro 'model' es requerido."})
    res = _ada_api("/api/ollama/details", params={"model": model})
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_memory_estimate(args: dict) -> str:
    """Estimate RAM/VRAM footprint for a model and context size."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "El parámetro 'model' es requerido."})
    params = {
        "model": model,
        "num_ctx": args.get("num_ctx", 4096),
        "max_tokens": args.get("max_tokens", 0),
        "batch": args.get("batch", 1),
    }
    res = _ada_api("/api/ollama/memory-estimate", params=params)
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_memory_calibrate(args: dict) -> str:
    """Calibrate memory footprint estimate for a model."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "El parámetro 'model' es requerido."})
    payload = {
        "model": model,
        "num_ctx": args.get("num_ctx", 4096),
        "max_tokens": args.get("max_tokens", 0),
        "batch": args.get("batch", 1),
    }
    res = _ada_api("/api/ollama/memory-calibrate", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_config_get(args: dict) -> str:
    """Get current Ollama timeout profile, thread limit, and context configurations."""
    res = _ada_api("/api/ollama/config")
    return json.dumps(res, indent=2, default=str)


def handle_ada_ollama_config_set(args: dict) -> str:
    """Update Ollama configurations and timeout profiles."""
    payload = dict(args)
    res = _ada_api("/api/ollama/config", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_models_catalog_list(args: dict) -> str:
    """List models in the ADA model catalog and available role categories."""
    res = _ada_api("/api/models/catalog")
    return json.dumps(res, indent=2, default=str)


def handle_ada_models_catalog_upsert(args: dict) -> str:
    """Add or update a model definition in the catalog."""
    name = args.get("name", "").strip()
    if not name:
        return json.dumps({"error": "El parámetro 'name' es requerido."})
    payload = {
        "name": name,
        "roles": args.get("roles", ["chat"]),
        "description": args.get("description", ""),
        "quality_tier": args.get("quality_tier", "medium"),
        "min_ram_gb": args.get("min_ram_gb", 4.0),
        "auto_pull": args.get("auto_pull", False),
    }
    res = _ada_api("/api/models/catalog", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_models_catalog_delete(args: dict) -> str:
    """Delete a model entry from the catalog."""
    name = args.get("name", "").strip()
    if not name:
        return json.dumps({"error": "El parámetro 'name' es requerido."})
    res = _ada_api("/api/models/catalog", method="DELETE", payload={"name": name})
    return json.dumps(res, indent=2, default=str)


def handle_ada_models_policy_get(args: dict) -> str:
    """Get current model selection mode and role assignments."""
    res = _ada_api("/api/models/policy")
    return json.dumps(res, indent=2, default=str)


def handle_ada_models_policy_set(args: dict) -> str:
    """Set model selection mode (manual, light, hybrid, turbo) and custom role bindings."""
    payload = dict(args)
    res = _ada_api("/api/models/policy", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_models_benchmark(args: dict) -> str:
    """Execute performance benchmark on a specified model."""
    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "El parámetro 'model' es requerido."})
    payload = {
        "model": model,
        "prompt_key": args.get("prompt_key", "quick"),
        "custom_prompt": args.get("custom_prompt"),
        "run_suite": args.get("run_suite", False),
        "prompt_keys": args.get("prompt_keys"),
    }
    res = _ada_api("/api/models/benchmark", method="POST", payload=payload, timeout=300.0)
    return json.dumps(res, indent=2, default=str)


def handle_ada_models_benchmark_prompts(args: dict) -> str:
    """List available benchmark prompt scenarios."""
    res = _ada_api("/api/models/benchmark/prompts")
    return json.dumps(res, indent=2, default=str)


# =============================================================================
# Tool Handlers: 4. MCP Servers Management
# =============================================================================

def handle_ada_mcp_list_servers(args: dict) -> str:
    """List all MCP servers configured in ADA and their execution status."""
    res = _ada_api("/api/mcps/servers")
    return json.dumps(res, indent=2, default=str)


def handle_ada_mcp_list_tools(args: dict) -> str:
    """List all available tools provided by connected MCP servers in ADA."""
    res = _ada_api("/api/mcps/tools")
    return json.dumps(res, indent=2, default=str)


def handle_ada_mcp_server_action(args: dict) -> str:
    """Perform action on an MCP server: start, stop, restart, ping."""
    name = args.get("name", "").strip()
    action = args.get("action", "ping").strip().lower()
    if not name:
        return json.dumps({"error": "El parámetro 'name' es requerido."})
    if action not in {"start", "stop", "restart", "ping"}:
        return json.dumps({"error": "La acción debe ser 'start', 'stop', 'restart' o 'ping'."})

    method = "GET" if action == "ping" else "POST"
    res = _ada_api(f"/api/mcps/servers/{name}/{action}", method=method, payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_mcp_restart_all(args: dict) -> str:
    """Restart all MCP servers managed by ADA."""
    res = _ada_api("/api/mcps/servers/restart-all", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


# =============================================================================
# Tool Handlers: 5. Healthcheck & Doctor
# =============================================================================

def handle_ada_healthcheck_diagnose(args: dict) -> str:
    """Run full diagnostic doctor check on ADA (dependencies, models, storage, runtime)."""
    res = _ada_api("/api/healthcheck")
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_auto_heal(args: dict) -> str:
    """Trigger automated self-healing routines to resolve detected issues."""
    res = _ada_api("/api/healthcheck/heal", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_fix(args: dict) -> str:
    """Execute a specific doctor fix action by ID (e.g. restart_agent, check_ollama, etc.)."""
    action_id = args.get("action_id", "").strip()
    if not action_id:
        return json.dumps({"error": "El parámetro 'action_id' es requerido."})
    res = _ada_api(f"/api/healthcheck/fix/{action_id}", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_prompts_list(args: dict) -> str:
    """List functional verification test cases from ADA's test catalog."""
    res = _ada_api("/api/healthcheck/prompts")
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_prompt_create(args: dict) -> str:
    """Create a new read-only functional verification test case."""
    prompt_id = args.get("id", "").strip()
    prompt_text = args.get("prompt", "").strip()
    if not prompt_id or not prompt_text:
        return json.dumps({"error": "Los parámetros 'id' y 'prompt' son requeridos."})
    payload = {
        "id": prompt_id,
        "prompt": prompt_text,
        "category": args.get("category", "general"),
        "expected": args.get("expected", ""),
        "expected_intent": args.get("expected_intent", ""),
        "max_seconds": args.get("max_seconds", 30),
    }
    res = _ada_api("/api/healthcheck/prompts", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_run_batch(args: dict) -> str:
    """Launch a durable background test batch run across prompts."""
    payload = {}
    if args.get("category"):
        payload["category"] = args.get("category")
    if args.get("prompt_ids"):
        payload["prompt_ids"] = args.get("prompt_ids")
    res = _ada_api("/api/healthcheck/run", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_batch_status(args: dict) -> str:
    """Get status, progress, and results of a healthcheck batch run."""
    run_id = args.get("run_id", "").strip()
    if not run_id:
        return json.dumps({"error": "El parámetro 'run_id' es requerido."})
    details = 1 if args.get("details", True) else 0
    res = _ada_api(f"/api/healthcheck/runs/{run_id}", params={"details": details})
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_batch_cancel(args: dict) -> str:
    """Cancel or interrupt a running healthcheck batch."""
    run_id = args.get("run_id", "").strip()
    if not run_id:
        return json.dumps({"error": "El parámetro 'run_id' es requerido."})
    res = _ada_api(f"/api/healthcheck/runs/{run_id}/cancel", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_history(args: dict) -> str:
    """Get history of completed test batch runs."""
    res = _ada_api("/api/healthcheck/history")
    return json.dumps(res, indent=2, default=str)


def handle_ada_healthcheck_latest(args: dict) -> str:
    """Get latest execution results per test prompt."""
    res = _ada_api("/api/healthcheck/latest")
    return json.dumps(res, indent=2, default=str)


# =============================================================================
# Tool Handlers: 6. Secure Vault & Credentials
# =============================================================================

def handle_ada_vault_list_keys(args: dict) -> str:
    """List the names of all secrets stored securely in SecureVault (vault.db)."""
    res = _ada_api("/api/vault/keys")
    return json.dumps(res, indent=2, default=str)


def handle_ada_vault_set_key(args: dict) -> str:
    """Store and encrypt a secret with AES-256 in the secure vault."""
    name = args.get("name", "").strip()
    value = args.get("value")
    if not name or value is None:
        return json.dumps({"error": "Los parámetros 'name' y 'value' son requeridos."})
    payload = {"name": name, "value": value, "meta": args.get("meta", {})}
    res = _ada_api("/api/vault/set", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_vault_delete_key(args: dict) -> str:
    """Delete a secret from SecureVault."""
    name = args.get("name", "").strip()
    if not name:
        return json.dumps({"error": "El parámetro 'name' es requerido."})
    res = _ada_api(f"/api/vault/{name}", method="DELETE")
    return json.dumps(res, indent=2, default=str)


def handle_ada_telegram_test(args: dict) -> str:
    """Test Telegram bot token connectivity against the official API."""
    token = args.get("token")
    if not token:
        try:
            from telegram.bot import resolve_telegram_token
            token = resolve_telegram_token()
        except Exception:
            token = None
    payload = {"token": token} if token else {}
    res = _ada_api("/api/telegram/test", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


# =============================================================================
# Tool Handlers: 7. System, Memory, Triggers, Presence, Updates & Telegram
# =============================================================================

def handle_ada_memory_stats(args: dict) -> str:
    """Get database memory statistics, learned procedures, sessions, and audit entries."""
    res = _ada_api("/api/memory/stats")
    return json.dumps(res, indent=2, default=str)


def handle_ada_memory_refiner_run(args: dict) -> str:
    """Trigger an immediate memory refinement and summarization cycle."""
    res = _ada_api("/api/memory/refiner/run", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_audit_log(args: dict) -> str:
    """Retrieve recent audit log entries from ADA."""
    limit = args.get("limit", 50)
    res = _ada_api("/api/audit", params={"limit": limit})
    return json.dumps(res, indent=2, default=str)


def handle_ada_triggers_list(args: dict) -> str:
    """List all registered system triggers (Telegram, Removable device, Calendar, Cron, Webhook)."""
    res = _ada_api("/api/triggers")
    return json.dumps(res, indent=2, default=str)


def handle_ada_trigger_toggle(args: dict) -> str:
    """Enable or disable a specific trigger."""
    name = args.get("trigger_name", "").strip()
    enable = bool(args.get("enable", True))
    if not name:
        return json.dumps({"error": "El parámetro 'trigger_name' es requerido."})
    res = _ada_api(f"/api/triggers/{name}/toggle", method="POST", payload={"enable": enable})
    return json.dumps(res, indent=2, default=str)


def handle_ada_trigger_status(args: dict) -> str:
    """Get detailed status of a specific trigger."""
    name = args.get("trigger_name", "").strip()
    if not name:
        return json.dumps({"error": "El parámetro 'trigger_name' es requerido."})
    res = _ada_api(f"/api/triggers/{name}/status")
    return json.dumps(res, indent=2, default=str)


def handle_ada_presence_get(args: dict) -> str:
    """Get current physical/logical presence and active device."""
    res = _ada_api("/api/presence")
    return json.dumps(res, indent=2, default=str)


def handle_ada_presence_set(args: dict) -> str:
    """Update presence location and reporting device."""
    location = args.get("location", "home")
    device = args.get("device", "manual")
    res = _ada_api("/api/presence", method="POST", payload={"location": location, "device": device})
    return json.dumps(res, indent=2, default=str)


def handle_ada_presence_history(args: dict) -> str:
    """Get historical presence logs."""
    res = _ada_api("/api/presence/history")
    return json.dumps(res, indent=2, default=str)


def handle_ada_telegram_service_status(args: dict) -> str:
    """Get Telegram background connector service status and bot identity."""
    res = _ada_api("/api/services/telegram/status")
    return json.dumps(res, indent=2, default=str)


def handle_ada_telegram_service_toggle(args: dict) -> str:
    """Start or stop the Telegram connector background service."""
    res = _ada_api("/api/services/telegram/toggle", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_telegram_service_config(args: dict) -> str:
    """Configure Telegram bot token and allowed chat IDs."""
    payload = {}
    if "token" in args:
        payload["token"] = args["token"]
    if "allowed_chat_ids" in args:
        payload["allowed_chat_ids"] = args["allowed_chat_ids"]
    res = _ada_api("/api/services/telegram/config", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_telegram_service_logs(args: dict) -> str:
    """Get recent logs from the Telegram connector service."""
    res = _ada_api("/api/services/telegram/logs")
    return json.dumps(res, indent=2, default=str)


def handle_ada_update_status(args: dict) -> str:
    """Get Git version info, active branch, and update status."""
    res = _ada_api("/api/update/status")
    return json.dumps(res, indent=2, default=str)


def handle_ada_update_check(args: dict) -> str:
    """Check for new commits/updates from upstream repository."""
    res = _ada_api("/api/update/check", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_update_apply(args: dict) -> str:
    """Apply the latest updates from git repository."""
    res = _ada_api("/api/update/apply", method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


def handle_ada_send_event(args: dict) -> str:
    """Dispatch an external trigger event into ADA's event bus."""
    topic = args.get("topic", "").strip()
    if not topic:
        return json.dumps({"error": "El parámetro 'topic' es requerido."})
    payload = {"topic": topic, "payload": args.get("payload", {})}
    res = _ada_api("/api/events", method="POST", payload=payload)
    return json.dumps(res, indent=2, default=str)


def handle_ada_monitoring_status(args: dict) -> str:
    """Check the runtime health, connectivity, and process status of Prometheus and Grafana."""
    res = _ada_api("/api/monitoring/status")
    return json.dumps(res, indent=2, default=str)


def handle_ada_monitoring_action(args: dict) -> str:
    """Start, stop, or restart Prometheus or Grafana."""
    action = args.get("action", "start").lower().strip()
    target = args.get("target", "all").lower().strip()

    if action not in {"start", "stop", "restart"}:
        return json.dumps({"error": "La acción debe ser 'start', 'stop' o 'restart'."})

    if target == "prometheus":
        endpoint = f"/api/monitoring/prometheus/{action}"
    elif target == "grafana":
        endpoint = f"/api/monitoring/grafana/{action}"
    elif target == "all":
        if action == "start":
            endpoint = "/api/monitoring/start-all"
        elif action == "stop":
            p = _ada_api("/api/monitoring/prometheus/stop", method="POST", payload={})
            g = _ada_api("/api/monitoring/grafana/stop", method="POST", payload={})
            return json.dumps({"prometheus": p, "grafana": g}, indent=2, default=str)
        else:
            p = _ada_api("/api/monitoring/prometheus/restart", method="POST", payload={})
            g = _ada_api("/api/monitoring/grafana/restart", method="POST", payload={})
            return json.dumps({"prometheus": p, "grafana": g}, indent=2, default=str)
    else:
        return json.dumps({"error": "El target debe ser 'all', 'prometheus' o 'grafana'."})

    res = _ada_api(endpoint, method="POST", payload={})
    return json.dumps(res, indent=2, default=str)


# =============================================================================
# Tool Definitions Metadata
# =============================================================================

TOOLS = [
    # 1. System & Identity
    {
        "name": "ada_status",
        "description": "Obtener el estado completo de ADA: versiones, commit, agente, salud de Ollama, motores disponibles, hardware, servidores MCP activos y métricas.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_status,
    },
    {
        "name": "ada_core_state",
        "description": "Obtener la topología en vivo del core de ADA, conectores activos (Telegram, Triggers, MCPs), modelos en uso y fases de actividad reciente.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_core_state,
    },
    {
        "name": "ada_activity",
        "description": "Obtener el estado de actividad y eventos en tiempo real de la ejecución de ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_activity,
    },
    {
        "name": "ada_restart_agent",
        "description": "Reiniciar el ciclo de vida del agente en memoria sin necesidad de reiniciar el servidor web de ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_restart_agent,
    },

    # 2. Chat & Interaction
    {
        "name": "ada_chat",
        "description": "Enviar un mensaje o solicitud a ADA para interactuar con el agente y ejecutar tareas directamente con todas sus capacidades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Mensaje o instrucción para ADA."},
                "lang": {"type": "string", "description": "Idioma preferido (por defecto 'es')."},
                "source": {"type": "string", "description": "Origen del mensaje (por defecto 'mcp-ide')."},
                "timeout_seconds": {"type": "number", "description": "Tiempo límite de espera en segundos (default: 300)."}
            },
            "required": ["message"]
        },
        "handler": handle_ada_chat,
    },
    {
        "name": "ada_conversation_get",
        "description": "Obtener el historial de mensajes de la conversación activa en la sesión actual.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_conversation_get,
    },
    {
        "name": "ada_conversation_clear",
        "description": "Limpiar el historial de conversación actual y liberar el contexto de carpetas en memoria.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_conversation_clear,
    },
    {
        "name": "ada_action_confirm",
        "description": "Confirmar una acción sensible pendiente que requiera autorización del usuario en ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_action_confirm,
    },
    {
        "name": "ada_action_cancel",
        "description": "Cancelar una acción sensible pendiente en ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_action_cancel,
    },
    {
        "name": "ada_debug_toggle",
        "description": "Activar o desactivar el registro de depuración detallado en ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enable": {"type": "boolean", "description": "True para activar, False para desactivar, omitir para alternar."}
            }
        },
        "handler": handle_ada_debug_toggle,
    },
    {
        "name": "ada_debug_events",
        "description": "Obtener los eventos recientes del registro de depuración de ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Cantidad máxima de eventos (default: 50)."},
                "session_id": {"type": "string", "description": "Filtrar por ID de sesión específico."}
            }
        },
        "handler": handle_ada_debug_events,
    },

    # 3. Models & Ollama
    {
        "name": "ada_ollama_status",
        "description": "Verificar el estado de conexión y salud del servidor Ollama y runtime de modelos locales.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_ollama_status,
    },
    {
        "name": "ada_ollama_list_models",
        "description": "Listar todos los modelos instalados en Ollama y los que se encuentran actualmente cargados en memoria.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_ollama_list_models,
    },
    {
        "name": "ada_ollama_load_model",
        "description": "Cargar explícitamente un modelo en memoria (VRAM/RAM) en Ollama.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo a cargar (e.g. 'llama3.2:3b')."}
            },
            "required": ["model"]
        },
        "handler": handle_ada_ollama_load_model,
    },
    {
        "name": "ada_ollama_unload_model",
        "description": "Descargar un modelo de la memoria para liberar VRAM/RAM en Ollama.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo a descargar."}
            },
            "required": ["model"]
        },
        "handler": handle_ada_ollama_unload_model,
    },
    {
        "name": "ada_ollama_preload_all",
        "description": "Precargar en memoria todos los modelos necesarios según la política de selección activa.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_ollama_preload_all,
    },
    {
        "name": "ada_ollama_delete_model",
        "description": "Eliminar un modelo local descargado en Ollama.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo a eliminar."}
            },
            "required": ["model"]
        },
        "handler": handle_ada_ollama_delete_model,
    },
    {
        "name": "ada_ollama_show_model",
        "description": "Obtener los detalles, modelfile, parámetros y arquitectura de un modelo en Ollama.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo a inspeccionar."}
            },
            "required": ["model"]
        },
        "handler": handle_ada_ollama_show_model,
    },
    {
        "name": "ada_ollama_memory_estimate",
        "description": "Calcular la estimación de consumo de memoria RAM/VRAM para un modelo dado su contexto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo."},
                "num_ctx": {"type": "integer", "description": "Tamaño del contexto en tokens (default: 4096)."},
                "max_tokens": {"type": "integer", "description": "Máximo de tokens a generar."},
                "batch": {"type": "integer", "description": "Batch size (default: 1)."}
            },
            "required": ["model"]
        },
        "handler": handle_ada_ollama_memory_estimate,
    },
    {
        "name": "ada_ollama_memory_calibrate",
        "description": "Calibrar experimentalmente la estimación de memoria de un modelo en Ollama.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo a calibrar."},
                "num_ctx": {"type": "integer", "description": "Tamaño de contexto a probar."},
                "max_tokens": {"type": "integer", "description": "Tokens de salida."},
                "batch": {"type": "integer", "description": "Batch size."}
            },
            "required": ["model"]
        },
        "handler": handle_ada_ollama_memory_calibrate,
    },
    {
        "name": "ada_ollama_config_get",
        "description": "Obtener la configuración actual de Ollama y el perfil de timeouts del agente.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_ollama_config_get,
    },
    {
        "name": "ada_ollama_config_set",
        "description": "Actualizar la configuración de Ollama (perfil de timeouts, límites de CPU, hilos, context window).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timeout_profile": {"type": "string", "enum": ["patient", "normal", "fast", "custom"], "description": "Perfil de timeout."},
                "cpu_limit_percent": {"type": "integer", "description": "Límite de CPU en porcentaje (10-100)."},
                "ollama_num_thread": {"type": "integer", "description": "Cantidad de hilos CPU."},
                "ollama_num_ctx": {"type": "integer", "description": "Ventana de contexto por defecto en tokens."},
                "ollama_keep_alive": {"type": "string", "description": "Tiempo de retención en memoria (e.g. '5m', '1h', '-1')."},
                "ollama_auto_unload": {"type": "boolean", "description": "Descargar modelo automáticamente tras inactividad."},
                "chat_timeout_seconds": {"type": "number", "description": "Timeout global de chat (si timeout_profile es custom)."}
            }
        },
        "handler": handle_ada_ollama_config_set,
    },
    {
        "name": "ada_models_catalog_list",
        "description": "Listar todos los modelos disponibles en el catálogo de ADA y los roles compatibles.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_models_catalog_list,
    },
    {
        "name": "ada_models_catalog_upsert",
        "description": "Agregar o actualizar la ficha de un modelo en el catálogo de ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del modelo en Ollama."},
                "roles": {"type": "array", "items": {"type": "string"}, "description": "Roles que puede cumplir (chat, fast, reasoning, vision, coder, etc.)."},
                "description": {"type": "string", "description": "Descripción del modelo."},
                "quality_tier": {"type": "string", "enum": ["low", "medium", "high", "best"], "description": "Tier de calidad."},
                "min_ram_gb": {"type": "number", "description": "RAM mínima requerida en GB."},
                "auto_pull": {"type": "boolean", "description": "Descargar automáticamente si no está disponible."}
            },
            "required": ["name"]
        },
        "handler": handle_ada_models_catalog_upsert,
    },
    {
        "name": "ada_models_catalog_delete",
        "description": "Eliminar un modelo del catálogo de ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del modelo a eliminar del catálogo."}
            },
            "required": ["name"]
        },
        "handler": handle_ada_models_catalog_delete,
    },
    {
        "name": "ada_models_policy_get",
        "description": "Obtener el modo de selección de modelos activo y las asignaciones por rol.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_models_policy_get,
    },
    {
        "name": "ada_models_policy_set",
        "description": "Configurar el modo de selección de modelos (manual, light, hybrid, turbo) y asignaciones de roles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "selection_mode": {"type": "string", "enum": ["manual", "light", "hybrid", "turbo"], "description": "Modo de selección."},
                "manual_policy": {"type": "object", "description": "Mapeo manual de roles a nombres de modelos (para modo manual)."}
            },
            "required": ["selection_mode"]
        },
        "handler": handle_ada_models_policy_set,
    },
    {
        "name": "ada_models_benchmark",
        "description": "Ejecutar un benchmark de rendimiento sobre un modelo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo a evaluar."},
                "prompt_key": {"type": "string", "description": "Clave del prompt del benchmark (e.g. 'quick', 'reasoning', 'coding', 'suite')."},
                "custom_prompt": {"type": "string", "description": "Prompt personalizado alternativo."},
                "run_suite": {"type": "boolean", "description": "Ejecutar suite completa de pruebas."}
            },
            "required": ["model"]
        },
        "handler": handle_ada_models_benchmark,
    },
    {
        "name": "ada_models_benchmark_prompts",
        "description": "Listar todos los prompts de prueba disponibles para benchmarks.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_models_benchmark_prompts,
    },

    # 4. MCP Servers Management
    {
        "name": "ada_mcp_list_servers",
        "description": "Listar todos los servidores MCP configurados en ADA y su estado de ejecución.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_mcp_list_servers,
    },
    {
        "name": "ada_mcp_list_tools",
        "description": "Listar todas las herramientas provistas por los servidores MCP de ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_mcp_list_tools,
    },
    {
        "name": "ada_mcp_server_action",
        "description": "Ejecutar una acción de control sobre un servidor MCP de ADA (start, stop, restart, ping).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del servidor MCP (e.g. 'filesystem', 'git', 'food', 'memory')."},
                "action": {"type": "string", "enum": ["start", "stop", "restart", "ping"], "description": "Acción a realizar."}
            },
            "required": ["name", "action"]
        },
        "handler": handle_ada_mcp_server_action,
    },
    {
        "name": "ada_mcp_restart_all",
        "description": "Reiniciar todos los servidores MCP gestionados por ADA simultáneamente.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_mcp_restart_all,
    },

    # 5. Healthcheck & Doctor
    {
        "name": "ada_healthcheck_diagnose",
        "description": "Ejecutar el diagnóstico de salud completo del Doctor de ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_healthcheck_diagnose,
    },
    {
        "name": "ada_healthcheck_auto_heal",
        "description": "Ejecutar las rutinas de autoreparación automática sobre los problemas detectados en ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_healthcheck_auto_heal,
    },
    {
        "name": "ada_healthcheck_fix",
        "description": "Ejecutar una acción de reparación puntual recomendada por el Doctor de ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_id": {"type": "string", "description": "ID de la acción de corrección."}
            },
            "required": ["action_id"]
        },
        "handler": handle_ada_healthcheck_fix,
    },
    {
        "name": "ada_healthcheck_prompts_list",
        "description": "Consultar la lista de casos de prueba funcionales registrados para verificar ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_healthcheck_prompts_list,
    },
    {
        "name": "ada_healthcheck_prompt_create",
        "description": "Registrar un nuevo caso de prueba funcional de solo lectura en ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Identificador único del caso."},
                "prompt": {"type": "string", "description": "Prompt de consulta/análisis a probar."},
                "category": {"type": "string", "description": "Categoría funcional (general, filesystem, memory, system, etc.)."},
                "expected": {"type": "string", "description": "Criterio de respuesta esperada."},
                "max_seconds": {"type": "number", "description": "Tiempo límite permitido en segundos."}
            },
            "required": ["id", "prompt"]
        },
        "handler": handle_ada_healthcheck_prompt_create,
    },
    {
        "name": "ada_healthcheck_run_batch",
        "description": "Iniciar la ejecución de un lote de pruebas funcionales en segundo plano.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filtrar por categoría específica (opcional)."},
                "prompt_ids": {"type": "array", "items": {"type": "string"}, "description": "Lista de IDs específicos a ejecutar (opcional)."}
            }
        },
        "handler": handle_ada_healthcheck_run_batch,
    },
    {
        "name": "ada_healthcheck_batch_status",
        "description": "Consultar el progreso, resultados detallados y trazas de un lote de pruebas funcionales.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "ID del lote de pruebas."},
                "details": {"type": "boolean", "description": "Incluir historial detallado (default: true)."}
            },
            "required": ["run_id"]
        },
        "handler": handle_ada_healthcheck_batch_status,
    },
    {
        "name": "ada_healthcheck_batch_cancel",
        "description": "Cancelar o interrumpir un lote de pruebas funcionales en ejecución.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "ID del lote a interrumpir."}
            },
            "required": ["run_id"]
        },
        "handler": handle_ada_healthcheck_batch_cancel,
    },
    {
        "name": "ada_healthcheck_history",
        "description": "Obtener el historial de lotes de verificación ejecutados.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_healthcheck_history,
    },
    {
        "name": "ada_healthcheck_latest",
        "description": "Obtener los últimos resultados consolidados por cada caso de prueba funcional.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_healthcheck_latest,
    },

    # 6. Secure Vault
    {
        "name": "ada_vault_list_keys",
        "description": "Listar los nombres de todos los secretos almacenados en la bóveda segura de ADA (vault.db).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_vault_list_keys,
    },
    {
        "name": "ada_vault_set_key",
        "description": "Guardar y cifrar un secreto o credencial en SecureVault con AES-256.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre o identificador del secreto."},
                "value": {"type": "string", "description": "Valor del secreto a cifrar."},
                "meta": {"type": "object", "description": "Metadatos adicionales opcionales."}
            },
            "required": ["name", "value"]
        },
        "handler": handle_ada_vault_set_key,
    },
    {
        "name": "ada_vault_delete_key",
        "description": "Eliminar un secreto de la bóveda segura de ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del secreto a eliminar."}
            },
            "required": ["name"]
        },
        "handler": handle_ada_vault_delete_key,
    },
    {
        "name": "ada_telegram_test",
        "description": "Probar la conectividad de un token de bot de Telegram contra la API oficial.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Token del bot (opcional, si se omite usa el guardado en vault/env)."}
            }
        },
        "handler": handle_ada_telegram_test,
    },

    # 7. System, Memory, Triggers, Presence, Updates & Telegram
    {
        "name": "ada_memory_stats",
        "description": "Obtener estadísticas de la base de datos de memoria de ADA, procedimientos aprendidos y sesiones.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_memory_stats,
    },
    {
        "name": "ada_memory_refiner_run",
        "description": "Disparar inmediatamente un ciclo de refinamiento y consolidación de memoria semántica en ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_memory_refiner_run,
    },
    {
        "name": "ada_audit_log",
        "description": "Obtener las entradas más recientes del registro de auditoría de ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Número de registros a obtener (default: 50)."}
            }
        },
        "handler": handle_ada_audit_log,
    },
    {
        "name": "ada_triggers_list",
        "description": "Listar los disparadores automáticos registrados (Telegram, Dispositivo extraíble, Calendario, Cron, Webhooks).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_triggers_list,
    },
    {
        "name": "ada_trigger_toggle",
        "description": "Activar o desactivar un disparador específico en ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "trigger_name": {"type": "string", "description": "Nombre del disparador (e.g. 'telegram', 'calendar', 'cron', 'removable-device')."},
                "enable": {"type": "boolean", "description": "True para activar, False para desactivar."}
            },
            "required": ["trigger_name", "enable"]
        },
        "handler": handle_ada_trigger_toggle,
    },
    {
        "name": "ada_trigger_status",
        "description": "Obtener el estado detallado de un disparador específico.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "trigger_name": {"type": "string", "description": "Nombre del disparador."}
            },
            "required": ["trigger_name"]
        },
        "handler": handle_ada_trigger_status,
    },
    {
        "name": "ada_presence_get",
        "description": "Obtener la ubicación física/lógica y dispositivo de presencia actual.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_presence_get,
    },
    {
        "name": "ada_presence_set",
        "description": "Actualizar la ubicación de presencia y dispositivo de reporte en ADA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Ubicación (e.g. 'home', 'office', 'travel')."},
                "device": {"type": "string", "description": "Dispositivo (e.g. 'desktop', 'mobile', 'manual')."}
            },
            "required": ["location"]
        },
        "handler": handle_ada_presence_set,
    },
    {
        "name": "ada_presence_history",
        "description": "Obtener el historial de cambios de presencia y ubicación.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_presence_history,
    },
    {
        "name": "ada_telegram_service_status",
        "description": "Obtener el estado del servicio daemon conector de Telegram y su bot.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_telegram_service_status,
    },
    {
        "name": "ada_telegram_service_toggle",
        "description": "Iniciar o detener el servicio en segundo plano conector de Telegram.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_telegram_service_toggle,
    },
    {
        "name": "ada_telegram_service_config",
        "description": "Configurar el token del bot de Telegram (cifrado en bóveda) y los IDs de chat autorizados.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Token del bot de Telegram."},
                "allowed_chat_ids": {"description": "Lista o string separado por comas de Chat IDs permitidos."}
            }
        },
        "handler": handle_ada_telegram_service_config,
    },
    {
        "name": "ada_telegram_service_logs",
        "description": "Obtener los registros recientes de eventos del conector de Telegram.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_telegram_service_logs,
    },
    {
        "name": "ada_update_status",
        "description": "Consultar la versión Git actual, commit y estado de actualización de ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_update_status,
    },
    {
        "name": "ada_update_check",
        "description": "Verificar en el repositorio remoto si existen nuevas actualizaciones de ADA.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_update_check,
    },
    {
        "name": "ada_update_apply",
        "description": "Descargar y aplicar la última actualización disponible de ADA desde Git.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_update_apply,
    },
    {
        "name": "ada_send_event",
        "description": "Enviar un evento externo al bus de eventos de ADA (disparadores, webhooks, notificaciones).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Nombre del tópico del evento (e.g. 'file.downloaded', 'system.alert')."},
                "payload": {"type": "object", "description": "Datos asociados al evento."}
            },
            "required": ["topic"]
        },
        "handler": handle_ada_send_event,
    },
    {
        "name": "ada_monitoring_status",
        "description": "Verificar el estado, conectividad HTTP y procesos de Prometheus (métricas) y Grafana (dashboards).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": handle_ada_monitoring_status,
    },
    {
        "name": "ada_monitoring_action",
        "description": "Levantar, detener o reiniciar Prometheus o Grafana.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["start", "stop", "restart"], "description": "Acción a realizar: 'start', 'stop' o 'restart'. Por defecto 'start'."},
                "target": {"type": "string", "enum": ["all", "prometheus", "grafana"], "description": "Servicio objetivo: 'all' (ambos), 'prometheus' o 'grafana'. Por defecto 'all'."}
            }
        },
        "handler": handle_ada_monitoring_action,
    },
]

TOOL_MAP = {t["name"]: t for t in TOOLS}


# =============================================================================
# JSON-RPC 2.0 Protocol Loop
# =============================================================================

def send_response(response: dict):
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main():
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except Exception as e:
            send_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "antigravity-ada-mcp",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            })
        elif method == "notifications/initialized" or method == "initialized":
            pass
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method == "tools/list":
            tool_list = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"]
                }
                for t in TOOLS
            ]
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": tool_list
                }
            })
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if tool_name not in TOOL_MAP:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
                })
            else:
                try:
                    result_text = TOOL_MAP[tool_name]["handler"](tool_args)
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result_text
                                }
                            ]
                        }
                    })
                except Exception as e:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "isError": True,
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Error executing {tool_name}: {e}"
                                }
                            ]
                        }
                    })
        else:
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                })


if __name__ == "__main__":
    main()
