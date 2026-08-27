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
            if (
                name in {"bash", "sh", "zsh", "fish"}
                or command.startswith(("/bin/", "/usr/bin/"))
                and name in {"bash", "sh", "zsh", "fish"}
            ):
                continue
            found.append({"pid": proc.info["pid"], "name": proc.info.get("name"), "command": command})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def _kind(command: str) -> str | None:
    import re

    value = command.casefold()
    if "telegram/bot.py" in value or "telegram\\bot.py" in value:
        return "telegram"
    if "ada.interfaces.web.server" in value or "ada.interfaces.web.asgi" in value or "ada:app" in value:
        return "ada"
    if "ollama serve" in value:
        return "ollama"
    if "mcps." in value or "mcps/" in value or "mcps\\" in value:
        m = re.search(r"mcps[\./\\]([a-zA-Z0-9_\-]+)", value)
        if m:
            return f"mcp:{m.group(1)}"
    if "mcp" in value and ("python" in value or "node" in value or "server" in value or "codex" in value):
        m = re.search(r"([a-zA-Z0-9_\-]+_mcp_server|[a-zA-Z0-9_\-]+mcp[a-zA-Z0-9_\-]*)", value)
        if m:
            return f"mcp:{m.group(1)}"
        return "mcp"
    if "prometheus" in value and ("--config.file" in value or "prometheus-local.yml" in value):
        return "prometheus"
    if "grafana" in value and ("--config=" in value or "grafana.ini" in value or "/usr/sbin/grafana" in value or "/usr/share/grafana" in value):
        return "grafana"
    return None


def detect_duplicates() -> Dict[str, Any]:
    """Return every detected instance, grouped by runtime kind."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in _processes():
        kind = _kind(item["command"])
        if kind:
            item["current_process"] = item["pid"] == os.getpid()
            groups.setdefault(kind, []).append(item)
    duplicates = {kind: items for kind, items in groups.items() if len(items) > 1}
    return {
        "ok": not bool(duplicates),
        "duplicates": duplicates,
        "instances": groups,
        "duplicate_count": sum(max(0, len(items) - 1) for items in groups.values()),
    }


def cleanup_duplicates() -> Dict[str, Any]:
    """Terminate redundant duplicate processes cleanly."""
    try:
        import psutil
    except ImportError:
        return {"ok": False, "error": "psutil not available"}
    report = detect_duplicates()
    killed = []
    current_pid = os.getpid()
    for kind, procs in report.get("duplicates", {}).items():
        keep_proc = None
        for p in procs:
            if p.get("current_process"):
                keep_proc = p
                break
        if not keep_proc and procs:
            keep_proc = procs[-1]

        for p in procs:
            if keep_proc and p["pid"] != keep_proc["pid"] and p["pid"] != current_pid:
                try:
                    proc = psutil.Process(p["pid"])
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed.append({"kind": kind, "pid": p["pid"]})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    return {"ok": True, "killed": killed, "remaining": detect_duplicates()}

