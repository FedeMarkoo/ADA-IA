"""Standalone Lightroom MCP server.

This module exposes the existing Lightroom manager as an independent MCP
server. ADA can consume it like any other MCP instead of owning Lightroom
operations directly.
"""

from ada.capabilities.photography.lightroom import run as _lightroom_run
from ada.infrastructure.integrations.mcp_server import serve


TOOL_SCHEMAS = {
    "lightroom_count_photos": {
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
    "lightroom_analyze": {
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
    "lightroom_plan": {
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "include_sofia": {"type": "boolean"},
            "only_route": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
    "lightroom_simulate": {
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "include_sofia": {"type": "boolean"},
            "only_route": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
    "lightroom_apply": {
        "type": "object",
        "required": ["confirm"],
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "include_sofia": {"type": "boolean"},
            "only_route": {"type": "string"},
            "confirm": {"type": "boolean", "const": True},
            "timeout": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
    "lightroom_recover": {
        "type": "object",
        "required": ["confirm"],
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "confirm": {"type": "boolean", "const": True},
            "timeout": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
}


def _call(action, args):
    payload = dict(args)
    payload["action"] = action
    return _lightroom_run(payload)


def _tools():
    return {
        "lightroom_count_photos": lambda args: _call("count", args),
        "lightroom_analyze": lambda args: _call("analyze", args),
        "lightroom_plan": lambda args: _call("plan", args),
        "lightroom_simulate": lambda args: _call("simulate", args),
        "lightroom_apply": lambda args: _call("organize", args),
        "lightroom_recover": lambda args: _call("recuperar", args),
    }


def main():
    tools = _tools()
    descriptions = {
        "lightroom_count_photos": "Count photos using the Lightroom manager without modifying files.",
        "lightroom_analyze": "Analyze the photo tree and SQLite state without modifying files.",
        "lightroom_plan": "Create a non-mutating Lightroom organization plan.",
        "lightroom_simulate": "Simulate Lightroom organization without modifying files.",
        "lightroom_apply": "Apply the planned Lightroom organization; explicit confirmation is required.",
        "lightroom_recover": "Recover Lightroom organization state; explicit confirmation is required.",
    }
    serve(tools, descriptions=descriptions, schemas=TOOL_SCHEMAS)


if __name__ == "__main__":
    main()
