#!/usr/bin/env python3
"""Minimal MCP server exposing public web search through DuckDuckGo."""

import html
import json
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOL = {
    "name": "web_search",
    "description": "Search the public internet and return result links and snippets.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 8},
        },
        "required": ["query"],
    },
}


def read_chunked_body(stream):
    chunks = []
    while True:
        size = int(stream.readline().split(b";", 1)[0], 16)
        if size == 0:
            stream.readline()
            return b"".join(chunks)
        chunks.append(stream.read(size))
        stream.readline()


def search(query, max_results):
    url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(url, headers={"User-Agent": "ADA-MCP-WebSearch/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        document = response.read().decode("utf-8", errors="replace")
    matches = re.findall(
        r'<a[^>]+href=[\'"]([^\'"]+)[\'"][^>]+class=[\'"]result-link[\'"][^>]*>(.*?)</a>.*?'
        r"class='result-snippet'[^>]*>(.*?)</td>",
        document,
        re.DOTALL,
    )
    results = []
    for link, title, snippet in matches[:max_results]:
        decoded_link = html.unescape(link)
        target = urllib.parse.parse_qs(urllib.parse.urlparse(decoded_link).query).get("uddg", [decoded_link])[0]
        results.append(
            {
                "title": re.sub(r"<[^>]+>", "", html.unescape(title)).strip(),
                "url": target,
                "snippet": re.sub(r"<[^>]+>", "", html.unescape(snippet)).strip(),
            }
        )
    return results


def rpc_response(request_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": request_id}
    payload["result" if error is None else "error"] = result if error is None else error
    return json.dumps(payload).encode()


class McpHandler(BaseHTTPRequestHandler):
    def read_request_body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            return read_chunked_body(self.rfile)
        return self.rfile.read(int(self.headers.get("Content-Length", "0")))

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
        body = self.read_request_body()
        message = json.loads(body)
        request_id = message.get("id")
        if request_id is None:
            self.send_response(202)
            self.end_headers()
            return
        method = message.get("method")
        params = message.get("params", {})
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ada-web-search", "version": "1.0.0"},
                }
            elif method == "tools/list":
                result = {"tools": [TOOL]}
            elif method == "tools/call" and params.get("name") == "web_search":
                arguments = params.get("arguments", {})
                query = str(arguments.get("query", "")).strip()
                if not query:
                    raise ValueError("query is required")
                limit = min(max(int(arguments.get("max_results", 5)), 1), 8)
                result = {
                    "content": [
                        {"type": "text", "text": json.dumps(search(query, limit), ensure_ascii=False)}
                    ],
                    "isError": False,
                }
            else:
                raise ValueError("unsupported MCP method or tool")
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
    ThreadingHTTPServer(("0.0.0.0", 8000), McpHandler).serve_forever()
