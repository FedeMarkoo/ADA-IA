#!/usr/bin/env python3
"""Read-only filesystem MCP server used by ADA."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def allowed_roots():
    configured = os.environ.get("ADA_FILESYSTEM_ALLOWED_ROOTS", "/data")
    return [Path(item).resolve() for item in configured.split(os.pathsep) if item]


def checked_path(path):
    target = Path(path).resolve()
    for root in allowed_roots():
        try:
            target.relative_to(root)
            return target
        except ValueError:
            continue
    raise PermissionError("path is outside the authorized filesystem roots")


def list_files(arguments):
    target = checked_path(arguments.get("path", ""))
    if not target.exists():
        return {"error": "path_not_found", "path": str(target)}
    if not target.is_dir():
        return {"error": "path_not_directory", "path": str(target)}
    recursive = bool(arguments.get("recursive", False))
    children = target.rglob("*") if recursive else target.iterdir()
    items = []
    for child in sorted(children):
        items.append(
            {
                "name": str(child.relative_to(target)) if recursive else child.name,
                "is_dir": child.is_dir(),
                "size_bytes": child.stat().st_size if child.is_file() else None,
            }
        )
    return {"path": str(target), "recursive": recursive, "total_items": len(items), "items": items}


def read_file(arguments):
    target = checked_path(arguments.get("path", ""))
    if not target.exists() or not target.is_file():
        return {"error": "file_not_found", "path": str(target)}
    max_bytes = int(arguments.get("max_bytes", 1048576))
    if max_bytes <= 0:
        return {"error": "max_bytes_must_be_positive"}
    size_bytes = target.stat().st_size
    if size_bytes > max_bytes:
        return {"error": "file_too_large", "path": str(target), "size_bytes": size_bytes, "max_bytes": max_bytes}
    return {"path": str(target), "content": target.read_bytes().decode("utf-8", errors="replace"), "size_bytes": size_bytes}


TOOL = {
    "name": "filesystem.list_files",
    "description": "Lists files and directories inside ADA's authorized filesystem roots.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory to inspect"},
            "recursive": {"type": "boolean", "default": False},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}

READ_FILE_TOOL = {
    "name": "filesystem.read_file",
    "description": "Reads a text file inside ADA's authorized filesystem roots.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to read"},
            "max_bytes": {"type": "integer", "minimum": 1, "default": 1048576},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}
TOOLS = [TOOL, READ_FILE_TOOL]


def response(request_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": request_id}
    payload["result" if error is None else "error"] = result if error is None else error
    return json.dumps(payload).encode()


class McpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/mcp":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/mcp":
            self.send_error(404)
            return
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        request_id = request.get("id")
        if request_id is None:
            self.send_response(202)
            self.end_headers()
            return
        method = request.get("method")
        params = request.get("params", {})
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ada-filesystem", "version": "1.0.0"},
                }
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call" and params.get("name") in {tool["name"] for tool in TOOLS}:
                arguments = params.get("arguments", {})
                tool_result = list_files(arguments) if params["name"] == TOOL["name"] else read_file(arguments)
                result = {
                    "content": [{"type": "text", "text": json.dumps(tool_result)}],
                    "isError": False,
                }
            else:
                raise ValueError("unsupported MCP method or tool")
            payload = response(request_id, result=result)
        except Exception as error:  # noqa: broad-exception-caught
            payload = response(request_id, error={"code": -32000, "message": str(error)})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), McpHandler).serve_forever()
