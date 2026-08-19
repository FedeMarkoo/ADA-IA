"""Validated configuration loading for ADA."""

import json
import os
from pathlib import Path


def _path(value, base):
    if not value:
        return value
    path = Path(os.path.expanduser(str(value)))
    return str(path if path.is_absolute() else (base / path).resolve())


def load_config(path=None, project_root=None):
    root = Path(project_root or Path(__file__).resolve().parents[2])
    config_path = Path(path or os.environ.get("ADA_CONFIG", root / "config.json")).expanduser()
    if not config_path.exists():
        return {"db_path": str(root / "memory.db"), "allowed_roots": [str(Path.home() / "Desktop")]}
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
    ):
        if key in config:
            config[key] = _path(config[key], root)
    config.setdefault("allowed_roots", [])
    if not isinstance(config["allowed_roots"], list):
        raise ValueError("allowed_roots debe ser una lista de carpetas.")
    config["allowed_roots"] = [_path(item, root) for item in config["allowed_roots"] if item]
    config.setdefault("confirm_risky", True)
    config.setdefault("allowed_commands", [])
    return config
