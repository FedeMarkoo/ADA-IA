"""Gmail capability backed by Google's official remote Gmail MCP server."""

from ada.infrastructure.integrations.mcp import MCPClient


CAPABILITY_SPEC = {
    "name": "gmail",
    "description": "Search and inspect Gmail, and create drafts through the Gmail MCP server.",
    "risk_level": "medium",
    "permissions": ("gmail.read",),
    "argument_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "get_thread", "create_draft"]},
            "query": {"type": "string"},
            "thread_id": {"type": "string"},
            "arguments": {"type": "object"},
            "confirm": {"type": "boolean"},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    "requires_confirmation": False,
}

_ACTION_TO_TOOL = {
    "search": "search_threads",
    "get_thread": "get_thread",
    "create_draft": "create_draft",
}


def run(args):
    action = args.get("action")
    tool = _ACTION_TO_TOOL.get(action)
    if not tool:
        return {"error": "invalid_gmail_action", "action": action}

    if action == "create_draft" and not args.get("confirm", False):
        return {
            "error": "confirmation_required",
            "action": action,
            "message": "Crear un borrador en Gmail requiere confirm: true.",
        }

    arguments = dict(args.get("arguments") or {})
    if action == "search" and args.get("query"):
        arguments.setdefault("query", args["query"])
    if action == "get_thread" and args.get("thread_id"):
        arguments.setdefault("thread_id", args["thread_id"])

    try:
        return MCPClient({"type": "http", "url": "https://gmailmcp.googleapis.com/mcp/v1", "headers": {
            "Authorization": "Bearer ${env:GMAIL_MCP_ACCESS_TOKEN}"
        }}).call(tool=tool, arguments=arguments)
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        return {"error": "gmail_mcp_execution_failed", "message": str(exc)}
