"""Validated configuration loading for ADA."""

import json
import os
from pathlib import Path


def _path(value, base):
    if not value:
        return value
    path = Path(os.path.expanduser(str(value)))
    return str(path if path.is_absolute() else (base / path).resolve())


def _env_flag(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _load_vscode_mcp(root):
    path = root / ".vscode" / "mcp.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Configuración MCP de VS Code inválida en {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(".vscode/mcp.json debe ser un objeto JSON.")
    servers = payload.get("servers", {})
    if not isinstance(servers, dict):
        raise ValueError(".vscode/mcp.json: servers debe ser un objeto.")
    return servers


def load_config(path=None, project_root=None):
    root = Path(project_root or Path(__file__).resolve().parents[2])
    config_path = Path(path or os.environ.get("ADA_CONFIG", root / "config.json")).expanduser()
    if not config_path.exists():
        return {
            "db_path": str(root / "memory.db"),
            "allowed_roots": [str(Path.home() / "Desktop")],
            "trust_workspace_mcp": _env_flag("ADA_TRUST_WORKSPACE_MCP"),
            "mcp_servers": _load_vscode_mcp(root) if _env_flag("ADA_TRUST_WORKSPACE_MCP") else {},
        }
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Configuración ADA inválida en {config_path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("La configuración ADA debe ser un objeto JSON.")
    config.setdefault("db_path", str(root / "memory.db"))
    config["db_path"] = _path(config["db_path"], root)
    for key in (
        "photo_root",
        "food_profile",
        "lightroom_script",
        "lightroom_db",
        "local_model_path",
        "gpt4all_model_path",
        "instagram_profile_dir",
    ):
        if key in config:
            config[key] = _path(config[key], root)
    config.setdefault("allowed_roots", [str(Path.home() / "Desktop")])
    if not isinstance(config["allowed_roots"], list):
        raise ValueError("allowed_roots debe ser una lista de carpetas.")
    config["allowed_roots"] = [_path(item, root) for item in config["allowed_roots"] if item]
    config.setdefault("trust_workspace_mcp", _env_flag("ADA_TRUST_WORKSPACE_MCP"))
    if "mcp_servers" not in config:
        if "mcpServers" in config:
            config["mcp_servers"] = config["mcpServers"]
        elif config["trust_workspace_mcp"]:
            config["mcp_servers"] = _load_vscode_mcp(root)
        else:
            config["mcp_servers"] = {}
    config.setdefault("confirm_risky", True)
    config.setdefault("memory_encryption", False)
    config.setdefault("allowed_commands", [])
    validate_config(config)
    return config


def validate_config(config):
    """Validate the public configuration contract before runtime construction."""
    if not isinstance(config, dict):
        raise ValueError("La configuración ADA debe ser un objeto JSON.")
    list_keys = ("allowed_roots", "allowed_commands", "engine_priority", "knowledge_files", "watch_folders")
    if "memory_encryption" in config and not isinstance(config["memory_encryption"], bool):
        raise ValueError("memory_encryption debe ser booleano.")
    for key in list_keys:
        if key in config and not isinstance(config[key], list):
            raise ValueError(f"{key} debe ser una lista.")
    for key in ("local_runtime", "models", "model_policy", "gpt4all", "telegram", "mcp_servers"):
        if key in config and not isinstance(config[key], dict):
            raise ValueError(f"{key} debe ser un objeto.")
    bool_keys = ("confirm_risky", "adaptive_models", "auto_pull_models", "trust_workspace_mcp")
    for key in bool_keys:
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} debe ser booleano.")
    string_keys = ("db_path", "photo_root", "food_profile", "instagram_profile_dir", "web_framework")
    for key in string_keys:
        if key in config and config[key] is not None and not isinstance(config[key], str):
            raise ValueError(f"{key} debe ser texto.")
    if "photo_executor" in config and config["photo_executor"] not in {"thread", "process"}:
        raise ValueError("photo_executor debe ser 'thread' o 'process'.")
    for key in ("backup_interval_seconds", "cpu_throttle_seconds", "cpu_throttle_max_wait_seconds"):
        if key in config:
            try:
                if float(config[key]) < 0:
                    raise ValueError(f"{key} no puede ser negativo.")
            except (TypeError, ValueError) as exc:
                if isinstance(exc, ValueError) and str(exc).startswith(key):
                    raise
                raise ValueError(f"{key} debe ser numérico.") from exc
    if "cpu_limit_percent" in config:
        try:
            cpu_limit = float(config["cpu_limit_percent"])
        except (TypeError, ValueError) as exc:
            raise ValueError("cpu_limit_percent debe ser numérico.") from exc
        if not 0 < cpu_limit <= 100:
            raise ValueError("cpu_limit_percent debe estar entre 0 y 100.")
    if "chat_workers" in config:
        try:
            chat_workers = int(config["chat_workers"])
        except (TypeError, ValueError) as exc:
            raise ValueError("chat_workers debe ser entero.") from exc
        if not 1 <= chat_workers <= 32:
            raise ValueError("chat_workers debe estar entre 1 y 32.")
    framework = config.get("web_framework", "flask")
    if framework not in {"flask", "asgi"}:
        raise ValueError("web_framework debe ser 'flask' o 'asgi'.")
    privacy = config.get("privacy_default", "normal")
    if privacy not in {"normal", "high"}:
        raise ValueError("privacy_default debe ser 'normal' o 'high'.")
    catalog = config.get("model_catalog", [])
    if not isinstance(catalog, (list, dict)):
        raise ValueError("model_catalog debe ser una lista u objeto de modelos.")
    entries = catalog if isinstance(catalog, list) else [dict(value, name=name) for name, value in catalog.items()]
    for item in entries:
        if not isinstance(item, dict) or not item.get("name"):
            raise ValueError("Cada modelo del catálogo necesita name.")
        for key in ("min_ram_gb", "min_vram_gb", "min_disk_free_gb"):
            if key in item and float(item[key]) < 0:
                raise ValueError(f"{key} no puede ser negativo.")
    return config
