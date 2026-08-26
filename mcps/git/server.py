"""Git MCP Server main entry point."""

import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcps.protocol import StdioMCPServer
from mcps.git.manager import GitManager


def create_git_server(repo_path: Optional[str] = None) -> StdioMCPServer:
    server = StdioMCPServer("git", "1.0.0")
    manager = GitManager(repo_path)

    server.register_tool(
        name="git.status",
        description="Obtiene el estado actual del repositorio Git (rama, archivos modificados, staged y untracked).",
        parameters={
            "type": "object",
            "properties": {},
        },
        handler=manager.status,
        risk_level="safe",
        requires_confirmation=False,
    )

    server.register_tool(
        name="git.log",
        description="Obtiene el historial de commits recientes del repositorio Git.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Número de commits a obtener", "default": 10}},
        },
        handler=manager.log,
        risk_level="safe",
        requires_confirmation=False,
    )

    server.register_tool(
        name="git.diff",
        description="Muestra las diferencias (diff) en el directorio de trabajo o en el área de preparación (stage).",
        parameters={
            "type": "object",
            "properties": {
                "staged": {
                    "type": "boolean",
                    "description": "Si es True, compara los cambios en stage",
                    "default": False,
                },
                "file": {"type": "string", "description": "Ruta específica de un archivo opcional"},
            },
        },
        handler=manager.diff,
        risk_level="safe",
        requires_confirmation=False,
    )

    server.register_tool(
        name="git.add",
        description="Agrega archivos modificados o nuevos al área de preparación (stage) de Git.",
        parameters={
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de rutas de archivos a agregar, o ['.'] para todos",
                    "default": ["."],
                }
            },
        },
        handler=manager.add,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    server.register_tool(
        name="git.commit",
        description="Realiza un commit de los cambios actualmente en stage con el mensaje provisto.",
        parameters={
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Mensaje descriptivo del commit"}},
            "required": ["message"],
        },
        handler=manager.commit,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    server.register_tool(
        name="git.branch",
        description="Lista las ramas disponibles o crea una nueva rama en el repositorio.",
        parameters={
            "type": "object",
            "properties": {"create": {"type": "string", "description": "Nombre de una nueva rama a crear (opcional)"}},
        },
        handler=manager.branch,
        risk_level="safe",
        requires_confirmation=False,
    )

    server.register_tool(
        name="git.push",
        description="Sube los commits locales al repositorio remoto (GitHub/GitLab).",
        parameters={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "description": "Nombre del remoto", "default": "origin"},
                "branch": {"type": "string", "description": "Rama a subir", "default": "main"},
                "set_upstream": {"type": "boolean", "description": "Establecer upstream (-u)", "default": False},
            },
        },
        handler=manager.push,
        risk_level="elevated",
        requires_confirmation=True,
    )

    server.register_tool(
        name="git.pull",
        description="Descarga e incorpora cambios desde el repositorio remoto.",
        parameters={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "description": "Nombre del remoto", "default": "origin"},
                "branch": {"type": "string", "description": "Rama a descargar", "default": "main"},
            },
        },
        handler=manager.pull,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    return server


if __name__ == "__main__":
    srv = create_git_server()
    srv.run()
