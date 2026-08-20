"""MCP client compatible with VS Code-style stdio and HTTP server definitions."""

from collections import deque
import ipaddress
import json
import os
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse


class MCPClient:
    _ENV_PATTERN = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")
    _PIPE_EOF = object()

    def __init__(self, server, timeout=60):
        self.server = server
        self.timeout = timeout

    @classmethod
    def _expand(cls, value):
        if not isinstance(value, str):
            return value
        return cls._ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)

    def _stdio_command(self):
        config = self.server if isinstance(self.server, dict) else {"command": self.server}
        command = config.get("command")
        if not command:
            raise ValueError("MCP stdio server requires command")
        if isinstance(command, str):
            command = [command]
        elif isinstance(command, (list, tuple)):
            command = list(command)
        else:
            raise ValueError("MCP command must be a string or list")
        args = config.get("args") or []
        if not isinstance(args, (list, tuple)):
            raise ValueError("MCP args must be a list")
        command = [str(self._expand(item)) for item in command + list(args)]
        if not command[0]:
            raise ValueError("MCP command cannot expand to an empty value")
        env = os.environ.copy()
        for key, value in (config.get("env") or {}).items():
            if value is not None:
                env[str(key)] = str(self._expand(value))
        cwd = self._expand(config.get("cwd"))
        return command, env, os.path.expanduser(cwd) if cwd else None

    @staticmethod
    def _pipes(proc):
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            raise RuntimeError("MCP process was started without stdio pipes")
        return proc.stdin, proc.stdout, proc.stderr

    @classmethod
    def _read_stdout(cls, stream, messages):
        """Drain stdout on a worker thread so pipe waits work on Windows too."""
        pending = bytearray()
        try:
            while True:
                chunk = os.read(stream.fileno(), 4096)
                if not chunk:
                    break
                pending.extend(chunk)
                while b"\n" in pending:
                    line, _, remainder = pending.partition(b"\n")
                    pending = bytearray(remainder)
                    if line.strip():
                        messages.put(bytes(line))
            if pending.strip():
                messages.put(bytes(pending))
        except (OSError, ValueError) as exc:
            messages.put(exc)
        finally:
            messages.put(cls._PIPE_EOF)

    @staticmethod
    def _read_stderr(stream, chunks):
        try:
            while True:
                chunk = os.read(stream.fileno(), 4096)
                if not chunk:
                    return
                chunks.append(chunk)
        except (OSError, ValueError):
            return

    @staticmethod
    def _stderr_text(chunks):
        return b"".join(chunks).decode("utf-8", errors="replace")[-1000:]

    def _request(self, proc, messages, stderr_chunks, request_id, method, params=None):
        stdin, _, _ = self._pipes(proc)
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        stdin.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise queue.Empty
                item = messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f"MCP timeout waiting for {method}") from exc
            if item is self._PIPE_EOF:
                raise RuntimeError("MCP server closed: " + self._stderr_text(stderr_chunks))
            if isinstance(item, Exception):
                raise RuntimeError(f"MCP stdout reader failed: {item}") from item
            try:
                message = json.loads(item.decode("utf-8"))
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("MCP server returned invalid JSON on stdout") from exc
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
        stdin, stdout, stderr = self._pipes(proc)
        messages: queue.Queue[object] = queue.Queue()
        stderr_chunks: deque[bytes] = deque(maxlen=128)
        readers = [
            threading.Thread(target=self._read_stdout, args=(stdout, messages), daemon=True),
            threading.Thread(target=self._read_stderr, args=(stderr, stderr_chunks), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            self._request(
                proc,
                messages,
                stderr_chunks,
                1,
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "ADA", "version": "0.1.0"},
                },
            )
            stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            stdin.flush()
            tools = self._request(proc, messages, stderr_chunks, 2, "tools/list", {}).get("tools", [])
            if list_only:
                return {"tools": tools}
            if not tool:
                return {"error": "tool is required", "tools": tools}
            return {
                "tool": tool,
                "result": self._request(
                    proc,
                    messages,
                    stderr_chunks,
                    3,
                    "tools/call",
                    {"name": tool, "arguments": arguments or {}},
                ),
            }
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            for reader in readers:
                reader.join(timeout=1)
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

    @staticmethod
    def _http_url(config):
        url = config.get("url") or config.get("serverUrl")
        if not isinstance(url, str) or not url:
            raise ValueError("MCP HTTP server requires url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MCP HTTP server requires a valid HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("MCP HTTP server URL cannot contain credentials")
        if parsed.scheme == "http" and not config.get("allow_insecure_http", False):
            try:
                loopback = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                loopback = parsed.hostname.lower() == "localhost"
            if not loopback:
                raise ValueError("Cleartext MCP HTTP is only allowed for loopback servers")
        return url

    def _http_call(self, tool=None, arguments=None, list_only=False):
        config = self.server if isinstance(self.server, dict) else {"url": self.server}
        url = self._http_url(config)
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
        if server_type == "http" or config.get("url") or config.get("serverUrl"):
            return self._http_call(tool, arguments, list_only)
        if server_type not in (None, "stdio"):
            raise ValueError(f"Unsupported MCP transport: {server_type}")
        return self._stdio_call(tool, arguments, list_only)
