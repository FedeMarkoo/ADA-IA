"""Filesystem MCP Server main entry point."""

import sys
from pathlib import Path
from typing import List, Optional

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcps.protocol import StdioMCPServer
from mcps.filesystem.handlers import FilesystemHandlers


def _photo_result(handlers, args):
    target = handlers.check_path(args.get("path", "."))
    recursive = args.get("recursive", True)
    paths = target.rglob("*") if recursive else target.iterdir()
    counts = handlers.photo_counts([p for p in paths if p.is_file()])
    return {"path": str(target), "photo_counts": counts, "summary": handlers.photo_summary(counts)}


def create_filesystem_server(allowed_dirs: Optional[List[str]] = None) -> StdioMCPServer:
    server = StdioMCPServer("filesystem", "1.0.0")
    handlers = FilesystemHandlers(allowed_dirs)

    server.register_tool(
        name="filesystem.list_files",
        description="Lista archivos y directorios dentro de las carpetas autorizadas. Por defecto solo inspecciona el nivel indicado; use recursive=true para incluir subdirectorios.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta del directorio"},
                "recursive": {"type": "boolean", "description": "Si es true, incluye elementos de todos los subdirectorios. Por defecto false.", "default": False},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=handlers.list_files,
        risk_level="safe",
    )

    server.register_tool(
        name="filesystem.photo_counts",
        description="Cuenta fotos de un evento por formato: XML, RAW y JPG. Puede incluir subcarpetas.",
        parameters={"type": "object", "properties": {"path": {"type": "string"}, "recursive": {"type": "boolean", "default": True}}, "required": ["path"]},
        handler=lambda args: _photo_result(handlers, args),
        risk_level="safe",
    )

    server.register_tool(
        name="filesystem.read_file",
        description="Lee el contenido de texto de un archivo permitido.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Ruta del archivo a leer"}},
            "required": ["path"],
        },
        handler=handlers.read_file,
        risk_level="safe",
    )

    server.register_tool(
        name="filesystem.write_file",
        description="Escribe o actualiza un archivo en una ruta permitida.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta de destino"},
                "content": {"type": "string", "description": "Contenido a escribir"},
            },
            "required": ["path", "content"],
        },
        handler=handlers.write_file,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    server.register_tool(
        name="filesystem.move_files",
        description="Mueve o renombra archivos dentro del almacenamiento autorizado.",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Ruta origen"},
                "destination": {"type": "string", "description": "Ruta destino"},
            },
            "required": ["source", "destination"],
        },
        handler=handlers.move_files,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    from mcps.filesystem.grouping import FileGrouper

    server.register_tool(
        name="filesystem.group_files",
        description="Agrupa y consolida archivos de una carpeta dentro de una subcarpeta nombrada con protección contra colisiones.",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Carpeta origen con archivos"},
                "name": {"type": "string", "description": "Nombre de la subcarpeta destino"},
                "allowed_roots": {"type": "array", "items": {"type": "string"}, "description": "Carpetas raíz permitidas"},
                "confirm": {"type": "boolean", "description": "Confirmación de ejecución"},
            },
            "required": ["source", "name"],
        },
        handler=FileGrouper.group_files,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    return server


if __name__ == "__main__":
    srv = create_filesystem_server()
    srv.run()
