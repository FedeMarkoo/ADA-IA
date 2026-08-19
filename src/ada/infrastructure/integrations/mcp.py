"""Small optional MCP stdio client using JSON-RPC over newline-delimited IO."""

import json
import subprocess
import selectors
import time


class MCPClient:
    def __init__(self, command, timeout=60):
        self.command = list(command)
        self.timeout = timeout

    def _request(self, proc, request_id, method, params=None):
        assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        proc.stdin.flush()
        while True:
            deadline = time.monotonic() + self.timeout
            selector = selectors.DefaultSelector()
            selector.register(proc.stdout, selectors.EVENT_READ)
            try:
                remaining = max(0, deadline - time.monotonic())
                if not selector.select(remaining):
                    raise TimeoutError(f"MCP timeout waiting for {method}")
                line = proc.stdout.readline()
            finally:
                selector.close()
            if not line:
                error = proc.stderr.read().decode("utf-8", errors="replace")
                raise RuntimeError("MCP server closed: " + error[-1000:])
            message = json.loads(line.decode("utf-8"))
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message.get("result", {})

    def call(self, tool=None, arguments=None, list_only=False):
        proc = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        try:
            self._request(
                proc,
                1,
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "ADA", "version": "0.1.0"},
                },
            )
            proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            proc.stdin.flush()
            tools = self._request(proc, 2, "tools/list", {}).get("tools", [])
            if list_only:
                return {"tools": tools}
            if not tool:
                return {"error": "tool is required", "tools": tools}
            return {
                "tool": tool,
                "result": self._request(proc, 3, "tools/call", {"name": tool, "arguments": arguments or {}}),
            }
        finally:
            proc.terminate()
            proc.wait(timeout=3)
