"""Safe adapter for the existing Lightroom photo manager.

ADA plans and simulates by default. Real operations are delegated to the
tested project script and require explicit confirmation.
"""

import os
import subprocess
import sys
from pathlib import Path

from ada.domain.policy import PolicyEngine, PolicyViolation


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPT = ROOT / "gestor_fotos_lightroom.py"
DEFAULT_RULES = ROOT / "REGLAS_GESTOR_FOTOS.md"
DEFAULT_DB = ROOT / "limpieza_lightroom.sqlite3"


def _run(command, timeout=3600):
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": "lightroom_timeout",
            "timeout": timeout,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "command": command,
        }
    except OSError as exc:
        return {
            "ok": False,
            "error": "lightroom_process_start_failed",
            "message": str(exc),
            "command": command,
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": command,
    }


def _path(value):
    return Path(os.path.expanduser(str(value))).resolve()


def _validate_paths(config, root, script, db, only_route=None):
    if not config.get("allowed_roots"):
        return {"error": "allowed_roots_required"}
    policy = PolicyEngine(config)
    try:
        policy.validate_paths([root, only_route])
    except PolicyViolation:
        return {"error": "path_outside_allowed_roots", "path": str(only_route or root)}

    allowed_scripts = (
        config["lightroom_allowed_scripts"]
        if "lightroom_allowed_scripts" in config
        else [config.get("lightroom_script") or DEFAULT_SCRIPT]
    )
    allowed_scripts = {_path(item) for item in allowed_scripts if item}
    if script not in allowed_scripts:
        return {"error": "lightroom_script_not_allowed", "script": str(script)}

    configured_db = _path(config.get("lightroom_db") or DEFAULT_DB)
    if db != configured_db and not policy.path_allowed(db):
        return {"error": "path_outside_allowed_roots", "path": str(db)}

    if only_route and only_route != root and root not in only_route.parents:
        return {"error": "route_outside_photo_root", "path": str(only_route), "root": str(root)}
    return None


def run(args):
    config = args.get("config") or {}
    action = str(args.get("action", "plan")).lower()
    root = _path(args.get("root", config.get("photo_root", "~/Desktop/Fotos")))
    script = _path(args.get("script", config.get("lightroom_script", DEFAULT_SCRIPT)))
    db = _path(args.get("db", config.get("lightroom_db", DEFAULT_DB)))
    only_route = _path(args["only_route"]) if args.get("only_route") else None
    path_error = _validate_paths(config, root, script, db, only_route)
    if path_error:
        return path_error
    try:
        timeout = int(args.get("timeout", config.get("lightroom_timeout", 3600)))
        maximum_timeout = int(config.get("lightroom_mcp_max_timeout", 3600))
    except (TypeError, ValueError):
        return {"error": "invalid_lightroom_timeout"}
    if timeout < 1 or timeout > maximum_timeout:
        return {"error": "invalid_lightroom_timeout", "maximum": maximum_timeout}
    if action in {"status", "estado", "summary", "resumen", "structure", "estructura", "folders", "carpetas"}:
        return {"error": "SQLite queries belong to the sqlite tool, not the Lightroom manager."}
    if not root.exists():
        return {"error": "photo root not found", "root": str(root)}
    if not script.exists():
        return {"error": "manager script not found", "script": str(script)}
    if action in {"organize", "mover", "limpiar", "recuperar"} and not args.get("confirm"):
        return {
            "error": "confirmation_required",
            "action": action,
            "root": str(root),
            "message": "Use plan/simulate first and confirm before changing Fotos.",
        }
    mode_map = {
        "count": "contar",
        "analyze": "analizar",
        "organize": "organizar",
        "plan": "organizar",
        "simulate": "organizar",
        "organizar": "organizar",
    }
    mode = mode_map.get(action, action)
    command = [sys.executable, str(script), "--modo", mode, "--root", str(root), "--db", str(db)]
    if action in {"plan", "simulate"}:
        command.append("--simular")
    if args.get("include_sofia"):
        command.append("--incluir-sofia")
    if only_route:
        command.extend(["--solo-ruta", str(only_route)])
    result = _run(command, timeout=timeout)
    result.update(
        {"skill": "lightroom", "action": action, "root": str(root), "safe_mode": action in {"plan", "simulate"}}
    )
    return result
