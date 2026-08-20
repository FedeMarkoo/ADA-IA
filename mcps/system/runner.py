"""System command execution with security allowlist validation."""

import shlex
import subprocess
from typing import Any, Dict, List, Optional

DEFAULT_ALLOWED_PREFIXES = [
    "echo", "ls", "dir", "git status", "git log", "uptime", "whoami", "date", "pytest", "python --version"
]


class SystemRunner:
    """Safely executes allowlisted system commands."""

    def __init__(self, allowed_prefixes: Optional[List[str]] = None):
        self.allowed_prefixes = allowed_prefixes or DEFAULT_ALLOWED_PREFIXES

    def run_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cmd = args.get("command", "").strip()
        if not cmd:
            return {"error": "Comando vacío"}

        allowed = any(cmd == p or cmd.startswith(p + " ") for p in self.allowed_prefixes)
        if not allowed:
            return {
                "error": f"Comando '{cmd}' no está en la lista de comandos autorizados.",
                "allowed_prefixes": self.allowed_prefixes,
            }

        try:
            res = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "command": cmd,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "ok": res.returncode == 0,
            }
        except Exception as exc:
            return {"command": cmd, "error": str(exc), "ok": False}
