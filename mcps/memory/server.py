"""MCP tools for managing ADA's persistent memory."""

from __future__ import annotations

from typing import Any, Dict

from mcps.protocol import StdioMCPServer


def _memory_or_error(memory, operation):
    if memory is None:
        return {"ok": False, "error": f"No hay un store de memoria disponible para {operation}."}
    return None


def create_memory_server(memory=None) -> StdioMCPServer:
    server = StdioMCPServer("memory", "1.0.0")

    def search(args: Dict[str, Any]) -> Dict[str, Any]:
        if error := _memory_or_error(memory, "consultar"):
            return error
        query = str(args.get("query", "")).strip()
        limit = min(max(int(args.get("limit", 10)), 1), 50)
        kind = args.get("kind")
        results = memory.search_memory_records(query, limit=limit, kind=kind)
        return {"ok": True, "count": len(results), "memories": results}

    def add(args: Dict[str, Any]) -> Dict[str, Any]:
        if error := _memory_or_error(memory, "agregar"):
            return error
        content = str(args.get("content", "")).strip()
        if not content and args.get("detail"):
            content = str(args["detail"]).strip()
        if not content:
            return {"ok": False, "error": "content no puede estar vacío."}
        memory_id = memory.add_memory_record(
            content,
            summary=args.get("summary", args.get("short")),
            kind=args.get("kind", "note"),
            meta=args.get("meta"),
        )
        return {"ok": True, "id": memory_id}

    def update(args: Dict[str, Any]) -> Dict[str, Any]:
        if error := _memory_or_error(memory, "modificar"):
            return error
        if not args.get("id"):
            return {"ok": False, "error": "id es obligatorio."}
        changed = memory.update_memory_record(
            int(args["id"]),
            content=args.get("content", args.get("detail")),
            summary=args.get("summary", args.get("short")),
            kind=args.get("kind"),
            meta=args.get("meta"),
        )
        return {"ok": changed, "id": int(args["id"]), "error": None if changed else "Memoria no encontrada."}

    def delete(args: Dict[str, Any]) -> Dict[str, Any]:
        if error := _memory_or_error(memory, "eliminar"):
            return error
        if not args.get("id"):
            return {"ok": False, "error": "id es obligatorio."}
        deleted = memory.delete_memory_record(int(args["id"]))
        return {"ok": deleted, "id": int(args["id"]), "error": None if deleted else "Memoria no encontrada."}

    common_kind = {"type": "string", "enum": ["note", "short_term", "episodic", "semantic", "profile", "knowledge"]}
    server.register_tool(
        "memory.search",
        "Consulta la memoria persistente de ADA por texto y opcionalmente por capa.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "kind": common_kind,
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
        search,
    )
    server.register_tool(
        "memory.add",
        "Agrega un recuerdo explícito a la memoria persistente de ADA.",
        {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Texto corto usado para seleccionar la memoria."},
                "content": {"type": "string", "description": "Detalle completo de la memoria."},
                "kind": common_kind,
                "meta": {"type": "object"},
            },
            "required": ["content"],
        },
        add,
        risk_level="confirmation",
        requires_confirmation=True,
    )
    server.register_tool(
        "memory.update",
        "Modifica el contenido, capa o metadatos de un recuerdo por id.",
        {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "summary": {"type": "string", "description": "Texto corto usado para seleccionar la memoria."},
                "content": {"type": "string"},
                "kind": common_kind,
                "meta": {"type": "object"},
            },
            "required": ["id"],
        },
        update,
        risk_level="confirmation",
        requires_confirmation=True,
    )
    server.register_tool(
        "memory.delete",
        "Elimina un recuerdo persistente por id.",
        {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
        delete,
        risk_level="confirmation",
        requires_confirmation=True,
    )
    return server


if __name__ == "__main__":
    create_memory_server().run()
