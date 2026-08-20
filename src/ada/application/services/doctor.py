"""Operational diagnostics and local setup helpers."""

import os
from pathlib import Path

from ada.infrastructure.runtime.ollama import LocalModelRuntime


def _ollama_check(config):
    runtime = LocalModelRuntime({**config, "local_runtime": {**config.get("local_runtime", {}), "auto_start": False}})
    status = runtime.status()
    models = runtime.installed_models() if status.available else []
    expected = sorted({value for value in (config.get("models") or {}).values() if value})
    return {
        "ok": status.available,
        "endpoint": runtime.endpoint,
        "reason": status.reason,
        "installed": models,
        "missing": [model for model in expected if model not in models],
    }


def diagnose(config):
    """Return safe, non-secret readiness checks for local integrations."""
    gmail_client = Path(os.path.expanduser(config.get("gmail_client_secret_path", "~/.config/ada/google-client.json")))
    gmail_token = Path(os.path.expanduser(config.get("gmail_token_path", "~/.config/ada/gmail-token.json")))
    profile = Path(os.path.expanduser(config.get("instagram_profile_dir", "~/.config/ada/instagram-profile")))
    instagram_ready = bool(
        config.get("instagram_user_id")
        and (config.get("instagram_access_token") or os.environ.get("INSTAGRAM_ACCESS_TOKEN"))
    )
    checks = {
        "ollama": _ollama_check(config),
        "gmail": {
            "ok": gmail_token.is_file()
            or (bool(config.get("gmail_credential_name")) and bool(os.environ.get("ADA_CREDENTIAL_KEY"))),
            "client_secret_present": gmail_client.is_file(),
            "token_present": gmail_token.is_file(),
            "credential_store": bool(config.get("gmail_credential_name")),
        },
        "instagram": {
            "ok": instagram_ready or bool(config.get("instagram_publish_script")),
            "graph_configured": instagram_ready,
            "puppeteer_script_present": bool(config.get("instagram_publish_script")),
            "profile_dir": str(profile),
            "profile_exists": profile.is_dir(),
        },
        "memory_encryption": {
            "ok": not bool(config.get("memory_encryption")) or bool(os.environ.get("ADA_MEMORY_KEY")),
            "enabled": bool(config.get("memory_encryption")),
            "key_present": bool(os.environ.get("ADA_MEMORY_KEY")),
        },
    }
    return {"ok": all(item.get("ok", True) for item in checks.values() if isinstance(item, dict)), "checks": checks}


def pull_models(config, models=None):
    """Explicitly download configured Ollama models; never pulls implicitly."""
    runtime = LocalModelRuntime(config)
    status = runtime.status()
    if not status.available:
        return {"ok": False, "error": "ollama_unavailable", "reason": status.reason}
    requested = models or sorted({value for value in (config.get("models") or {}).values() if value})
    installed = set(runtime.installed_models())
    pulled = [model for model in requested if model not in installed and runtime.pull_model(model)]
    missing = [model for model in requested if model not in installed and model not in pulled]
    return {"ok": not missing, "requested": requested, "pulled": pulled, "missing": missing}


def prepare_instagram_profile(config):
    """Create a private browser profile directory for Puppeteer sessions."""
    profile = Path(os.path.expanduser(config.get("instagram_profile_dir", "~/.config/ada/instagram-profile")))
    profile.mkdir(parents=True, exist_ok=True)
    try:
        profile.chmod(0o700)
    except OSError:
        pass
    return {"ok": True, "profile_dir": str(profile), "mode": oct(profile.stat().st_mode & 0o777)}
