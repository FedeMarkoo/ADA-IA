"""Git operations capability bridge delegating to mcps.git."""

from typing import Any, Dict
from mcps.git.manager import GitManager

CAPABILITY_SPEC = {
    "name": "git",
    "description": "Control de versiones Git (status, log, diff, add, commit, branch, push, pull).",
    "risk_level": "medium",
    "permissions": ["system.command", "filesystem.write"],
    "requires_confirmation": False,
    "argument_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "log", "diff", "add", "commit", "branch", "push", "pull"],
                "default": "status",
            },
            "message": {"type": "string", "description": "Mensaje de commit"},
            "files": {"type": "array", "items": {"type": "string"}, "description": "Archivos para git add"},
            "limit": {"type": "integer", "description": "Límite de commits para log", "default": 10},
            "staged": {"type": "boolean", "description": "Diff de staged changes", "default": False},
            "branch": {"type": "string", "description": "Nombre de la rama"},
            "remote": {"type": "string", "description": "Nombre del remoto", "default": "origin"},
        },
    },
    "version": "1.0.0",
}


def run(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "status")
    manager = GitManager(args.get("repo_path"))

    if action == "status":
        return manager.status(args)
    elif action == "log":
        return manager.log(args)
    elif action == "diff":
        return manager.diff(args)
    elif action == "add":
        return manager.add(args)
    elif action == "commit":
        return manager.commit(args)
    elif action == "branch":
        return manager.branch(args)
    elif action == "push":
        return manager.push(args)
    elif action == "pull":
        return manager.pull(args)
    else:
        return {"error": f"Acción git desconocida: {action}"}
