"""Standalone Lightroom MCP server.

This module exposes the canonical Lightroom adapter to external MCP clients.
ADA itself uses the same adapter directly, avoiding duplicate implementations.
"""

import logging
import os

from ada.capabilities.photography.lightroom import run as _lightroom_run
from ada.config import load_config
from ada.infrastructure.integrations.mcp_server import serve
from ada.infrastructure.persistence.sqlite import Memory


logger = logging.getLogger("ada.lightroom_mcp")


TOOL_SCHEMAS = {
    "lightroom_count_photos": {
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
        },
        "additionalProperties": False,
    },
    "lightroom_analyze": {
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "script": {"type": "string"},
            "db": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
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
            "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
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
            "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
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
            "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
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
            "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
        },
        "additionalProperties": False,
    },
}


def _audit(audit, action, args, result):
    if audit is None:
        return
    summary_keys = ("ok", "error", "returncode", "action", "root", "safe_mode")
    summary = {key: result[key] for key in summary_keys if isinstance(result, dict) and key in result}
    success = not bool(isinstance(result, dict) and result.get("error"))
    if isinstance(result, dict) and result.get("ok") is False:
        success = False
    try:
        audit.record_audit(
            f"lightroom_mcp.{action}",
            request={"action": action, "arguments": args},
            result=summary,
            success=success,
            actor="lightroom_mcp",
        )
    except Exception as exc:
        logger.warning("lightroom_mcp_audit_failed action=%s error=%s", action, exc)


def _call(action, args, config, audit=None):
    payload = dict(args)
    payload["action"] = action
    payload["config"] = config
    result = _lightroom_run(payload)
    _audit(audit, action, args, result)
    return result


def _tools(config=None, audit=None):
    config = dict(config or load_config())
    return {
        "lightroom_count_photos": lambda args: _call("count", args, config, audit),
        "lightroom_analyze": lambda args: _call("analyze", args, config, audit),
        "lightroom_plan": lambda args: _call("plan", args, config, audit),
        "lightroom_simulate": lambda args: _call("simulate", args, config, audit),
        "lightroom_apply": lambda args: _call("organize", args, config, audit),
        "lightroom_recover": lambda args: _call("recuperar", args, config, audit),
    }


def main():
    config = load_config()
    audit = Memory(
        config.get("db_path", "memory.db"),
        encrypted=bool(config.get("memory_encryption", False)),
        encryption_key=os.environ.get("ADA_MEMORY_KEY"),
    )
    tools = _tools(config, audit)
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
