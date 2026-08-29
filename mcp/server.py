#!/usr/bin/env python3
"""HTTP gateway exposing all ADA MCP servers from one container."""

import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from filesystem import server as filesystem


def load_web_search():
    path = Path(__file__).parent / "web-search" / "server.py"
    spec = importlib.util.spec_from_file_location("ada_web_search_server", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


web_search = load_web_search()
SERVERS = {
    "/filesystem": {"name": "ada-filesystem", "tools": filesystem.TOOLS},
    "/web-search": {"name": "ada-web-search", "tools": [web_search.TOOL]},
}


def call_tool(path, tool_name, arguments):
    if path == "/filesystem":
        known = {tool["name"] for tool in filesystem.TOOLS}
        if tool_name not in known:
            raise ValueError("unsupported MCP tool")
        return filesystem.list_files(arguments) if tool_name == "filesystem.list_files" else filesystem.read_file(arguments)
    if path == "/web-search" and tool_name == "web_search":
        return web_search.search(arguments.get("query", ""), min(max(int(arguments.get("max_results", 5)), 1), 8))
    raise ValueError("unsupported MCP tool")


def rpc_response(request_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": request_id}
    payload["result" if error is None else "error"] = result if error is None else error
    return json.dumps(payload).encode()


class McpGatewayHandler(BaseHTTPRequestHandler):
    def server_config(self):
        return SERVERS.get(self.path.split("?", 1)[0])

    def do_GET(self):
        if self.server_config():
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_error(404)

    def do_POST(self):
        config = self.server_config()
        if config is None:
            self.send_error(404)
            return
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        request_id = request.get("id")
        if request_id is None:
            self.send_response(202)
            self.end_headers()
            return
        try:
            method = request.get("method")
            params = request.get("params", {})
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": config["name"], "version": "1.0.0"},
                }
            elif method == "tools/list":
                result = {"tools": config["tools"]}
            elif method == "tools/call":
                value = call_tool(self.path.split("?", 1)[0], params.get("name"), params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}
            else:
                raise ValueError("unsupported MCP method")
            payload = rpc_response(request_id, result=result)
        except Exception as error:  # noqa: broad-exception-caught
            payload = rpc_response(request_id, error={"code": -32000, "message": str(error)})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), McpGatewayHandler).serve_forever()
