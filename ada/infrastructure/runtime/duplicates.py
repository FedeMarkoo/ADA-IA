"""Best-effort detection of duplicate ADA-owned runtimes and listeners."""

from __future__ import annotations

import os
from typing import Any, Dict, List


def _processes() -> List[Dict[str, Any]]:
    try:
        import psutil
    except ImportError:
        return []
    found = []
    for proc in psutil.process_iter(["pid", "cmdline", "name"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            command = " ".join(str(part) for part in cmdline)
            if not command:
                continue
            # Ignore shells/diagnostic commands whose search text happens to
            # contain a runtime name (for example `pgrep telegram/bot.py`).
            name = str(proc.info.get("name") or "").casefold()
            if name in {"bash", "sh", "zsh", "fish"} or command.startswith(("/bin/", "/usr/bin/")) and name in {"bash", "sh", "zsh", "fish"}:
                continue
            found.append({"pid": proc.info["pid"], "name": proc.info.get("name"), "command": command})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def _kind(command: str) -> str | None:
    value = command.casefold()
    if "telegram/bot.py" in value or "telegram\\bot.py" in value:
        return "telegram"
    if "ada.interfaces.web.server" in value or "ada.interfaces.web.asgi" in value:
        return "ada"
    if "ollama serve" in value:
        return "ollama"
    if "mcp" in value and ("python" in value or "node" in value or "server" in value):
        return "mcp"
    return None


def detect_duplicates() -> Dict[str, Any]:
    """Return every detected instance, grouped by runtime kind."""
    groups: Dict[str, List[Dict[str, Any]]] = {kind: [] for kind in ("ada", "telegram", "mcp", "ollama")}
    for item in _processes():
        kind = _kind(item["command"])
        if kind:
            item["current_process"] = item["pid"] == os.getpid()
            groups[kind].append(item)
    duplicates = {
        kind: items for kind, items in groups.items() if len(items) > 1
    }
    return {
        "ok": not bool(duplicates),
        "duplicates": duplicates,
        "instances": groups,
        "duplicate_count": sum(max(0, len(items) - 1) for items in groups.values()),
    }
