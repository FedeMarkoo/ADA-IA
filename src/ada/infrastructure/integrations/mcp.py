"""MCP client compatible with VS Code-style stdio and HTTP server definitions."""

import json
import os
import selectors
import shlex
import subprocess
import time
import urllib.error
import urllib.request


class MCPClient:
    def __init__(self, server, timeout=60):
        self.server = server
        self.timeout = timeout

    @staticmethod
    def _expand(value):
        if not isinstance(value, str):
            return value
        if value.startswith("${env:") and value.endswith("}"):
            return os.environ.get(value[6:-1], "")
        return value

    def _stdio_command(self):
        config = self.server if isinstance(self.server, dict) else {"command": self.server}
        command = config.get("command")
        if not command:
            raise ValueError("MCP stdio server requires command")
        if isinstance(command, str):
            command = shlex.split(command)
        if not isinstance(command, (list, tuple)):
            raise ValueError("MCP command must be a string or list")
        args = config.get("args") or []
        command = [self._expand(item) for item in list(command) + list(args)]
        env = os.environ.copy()
        for key, value in (config.get("env") or {}).items():
            if value is not None:
                env[str(key)] = str(self._expand(value))
        cwd = config.get("cwd")
        return command, env, os.path.expanduser(cwd) if cwd else None

    def _request(self, proc, request_id, method, params=None):
        assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        proc.stdin.flush()
        deadline = time.monotonic() + self.timeout
        while True:
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

    def _stdio_call(self, tool=None, arguments=None, list_only=False):
        command, env, cwd = self._stdio_command()
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
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
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()

    @staticmethod
    def _read_http_response(response):
        body = response.read().decode("utf-8", errors="replace")
        content_type = response.headers.get("Content-Type", "")
        if "text/event-stream" not in content_type:
            return json.loads(body) if body else {}
        data = []
        for line in body.splitlines():
            if line.startswith("data:"):
                value = line[5:].strip()
                if value:
                    data.append(value)
        for value in reversed(data):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                continue
        raise RuntimeError("MCP HTTP server returned an invalid event stream")

    def _http_request(self, url, payload, headers):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **headers,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                result = self._read_http_response(response)
                return result, session_id
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"MCP HTTP error {exc.code}: {detail[-1000:]}") from exc

    def _http_call(self, tool=None, arguments=None, list_only=False):
        config = self.server if isinstance(self.server, dict) else {"url": self.server}
        url = config.get("url") or config.get("serverUrl")
        if not url:
            raise ValueError("MCP HTTP server requires url")
        headers = {str(k): str(self._expand(v)) for k, v in (config.get("headers") or {}).items()}
        initialize = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": config.get("protocolVersion", "2025-06-18"),
                "capabilities": {},
                "clientInfo": {"name": "ADA", "version": "0.1.0"},
            },
        }
        result, session_id = self._http_request(url, initialize, headers)
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        self._http_request(
            url,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers,
        )
        tools_result, _ = self._http_request(
            url,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers,
        )
        tools = tools_result.get("result", {}).get("tools", [])
        if list_only:
            return {"tools": tools}
        if not tool:
            return {"error": "tool is required", "tools": tools}
        result, _ = self._http_request(
            url,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments or {}},
            },
            headers,
        )
        return {"tool": tool, "result": result.get("result", result)}

    def call(self, tool=None, arguments=None, list_only=False):
        config = self.server if isinstance(self.server, dict) else {"command": self.server}
        server_type = config.get("type")
        if server_type == "http" or config.get("url"):
            return self._http_call(tool, arguments, list_only)
        if server_type not in (None, "stdio"):
            raise ValueError(f"Unsupported MCP transport: {server_type}")
        return self._stdio_call(tool, arguments, list_only)
