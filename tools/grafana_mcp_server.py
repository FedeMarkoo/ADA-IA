#!/usr/bin/env python3
"""
Grafana Model Context Protocol (MCP) Server for Antigravity.
Implements the standard MCP JSON-RPC 2.0 protocol over stdio to manage Grafana.
"""

import sys
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
import os
from pathlib import Path

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000").rstrip("/")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_PASSWORD", "admin")
AUTH_HEADER = "Basic " + base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASSWORD}".encode("ascii")).decode("ascii")


def _grafana_api(endpoint: str, method: str = "GET", payload: dict = None) -> dict:
    """Execute a request against the Grafana REST API."""
    url = f"{GRAFANA_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", AUTH_HEADER)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {"ok": True}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        try:
            parsed = json.loads(err_body)
            return {"error": True, "code": e.code, "message": parsed.get("message", err_body)}
        except Exception:
            return {"error": True, "code": e.code, "message": err_body}
    except Exception as e:
        return {"error": True, "message": str(e)}


# =============================================================================
# Tool Implementations
# =============================================================================

def handle_grafana_health(args: dict) -> str:
    """Check Grafana health and version."""
    res = _grafana_api("/api/health")
    org_res = _grafana_api("/api/org")
    return json.dumps({
        "status": "connected" if "error" not in res else "offline",
        "grafana_url": GRAFANA_URL,
        "health": res,
        "organization": org_res
    }, indent=2)


def handle_grafana_list_dashboards(args: dict) -> str:
    """Search and list dashboards in Grafana."""
    query = args.get("query", "")
    tag = args.get("tag", "")
    params = []
    if query:
        params.append(f"query={urllib.parse.quote(query)}")
    if tag:
        params.append(f"tag={urllib.parse.quote(tag)}")
    endpoint = "/api/search?" + "&".join(params) if params else "/api/search"
    res = _grafana_api(endpoint)
    return json.dumps(res, indent=2)


def handle_grafana_get_dashboard(args: dict) -> str:
    """Get full dashboard definition by UID."""
    uid = args.get("uid", "ada-overview")
    res = _grafana_api(f"/api/dashboards/uid/{uid}")
    return json.dumps(res, indent=2)


def handle_grafana_save_dashboard(args: dict) -> str:
    """Create or update a dashboard in Grafana."""
    dashboard = args.get("dashboard")
    if isinstance(dashboard, str):
        try:
            dashboard = json.loads(dashboard)
        except Exception as e:
            return json.dumps({"error": f"Invalid dashboard JSON string: {e}"})

    if not dashboard or not isinstance(dashboard, dict):
        return json.dumps({"error": "dashboard object is required"})

    dashboard["editable"] = True
    message = args.get("message", "Updated via Antigravity Grafana MCP")
    overwrite = args.get("overwrite", True)

    payload = {
        "dashboard": dashboard,
        "overwrite": overwrite,
        "message": message
    }
    res = _grafana_api("/api/dashboards/db", method="POST", payload=payload)
    return json.dumps(res, indent=2)


def handle_grafana_sync_dashboard_file(args: dict) -> str:
    """Read a local dashboard JSON file and import/push it to Grafana."""
    file_path = args.get("file_path", "monitoring/grafana/dashboards/ada-overview.json")
    path = Path(file_path).resolve()
    if not path.is_file():
        return json.dumps({"error": f"Dashboard file not found: {file_path}"})

    try:
        content = path.read_text(encoding="utf-8")
        dashboard = json.loads(content)
    except Exception as e:
        return json.dumps({"error": f"Failed to parse JSON file {file_path}: {e}"})

    dashboard["editable"] = True
    message = args.get("message", f"Synchronized from {file_path} via Antigravity MCP")
    overwrite = args.get("overwrite", True)

    payload = {
        "dashboard": dashboard,
        "overwrite": overwrite,
        "message": message
    }
    save_res = _grafana_api("/api/dashboards/db", method="POST", payload=payload)

    # Ensure public dashboard token
    uid = dashboard.get("uid", "ada-overview")
    pub_res = _grafana_api(f"/api/dashboards/uid/{uid}/public-dashboards")
    public_url = None
    if not pub_res.get("error") and pub_res.get("accessToken"):
        public_url = f"{GRAFANA_URL}/public-dashboards/{pub_res.get('accessToken')}"
    elif pub_res.get("error"):
        create_pub = _grafana_api(f"/api/dashboards/uid/{uid}/public-dashboards", method="POST", payload={
            "isEnabled": True,
            "timeSelectionEnabled": True,
            "annotationsEnabled": False,
            "share": "public"
        })
        if create_pub.get("accessToken"):
            public_url = f"{GRAFANA_URL}/public-dashboards/{create_pub.get('accessToken')}"

    return json.dumps({
        "success": not save_res.get("error"),
        "file_path": str(path),
        "save_result": save_res,
        "public_url": public_url,
        "dashboard_url": f"{GRAFANA_URL}/d/{uid}"
    }, indent=2)


def handle_grafana_export_dashboard_file(args: dict) -> str:
    """Fetch live dashboard from Grafana and save/export it to a local JSON file."""
    uid = args.get("uid", "ada-overview")
    file_path = args.get("file_path", "monitoring/grafana/dashboards/ada-overview.json")

    res = _grafana_api(f"/api/dashboards/uid/{uid}")
    if res.get("error"):
        return json.dumps({"error": f"Failed to fetch dashboard {uid} from Grafana: {res}"})

    dashboard = res.get("dashboard", res)
    if "id" in dashboard:
        dashboard["id"] = None

    target_path = Path(file_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return json.dumps({
            "success": True,
            "uid": uid,
            "title": dashboard.get("title"),
            "version": dashboard.get("version"),
            "total_panels": len(dashboard.get("panels", [])),
            "file_path": str(target_path)
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to write dashboard to {file_path}: {e}"})


def handle_grafana_list_datasources(args: dict) -> str:
    """List all configured datasources in Grafana."""
    res = _grafana_api("/api/datasources")
    return json.dumps(res, indent=2)


def handle_grafana_manage_public_dashboard(args: dict) -> str:
    """Get or create a public dashboard token (Share externally)."""
    uid = args.get("dashboard_uid", "ada-overview")
    action = args.get("action", "get_or_create")

    # Check existing
    res = _grafana_api(f"/api/dashboards/uid/{uid}/public-dashboards")
    if action == "get" or (action == "get_or_create" and not res.get("error")):
        return json.dumps(res, indent=2)

    # Create
    payload = {
        "isEnabled": True,
        "timeSelectionEnabled": True,
        "annotationsEnabled": False,
        "share": "public"
    }
    create_res = _grafana_api(f"/api/dashboards/uid/{uid}/public-dashboards", method="POST", payload=payload)
    return json.dumps(create_res, indent=2)


# Tool definitions metadata
TOOLS = [
    {
        "name": "grafana_health",
        "description": "Check Grafana connectivity, version, health status, and organization info.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
        "handler": handle_grafana_health
    },
    {
        "name": "grafana_list_dashboards",
        "description": "Search and list dashboards configured in Grafana by title query or tag.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional search term for dashboard title"},
                "tag": {"type": "string", "description": "Optional tag filter"}
            }
        },
        "handler": handle_grafana_list_dashboards
    },
    {
        "name": "grafana_get_dashboard",
        "description": "Fetch the complete JSON definition, layout, and panel configurations of a Grafana dashboard by its UID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "The UID of the dashboard (e.g. 'ada-overview')"}
            },
            "required": ["uid"]
        },
        "handler": handle_grafana_get_dashboard
    },
    {
        "name": "grafana_save_dashboard",
        "description": "Create or update a dashboard in Grafana given its JSON structure directly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dashboard": {"type": "object", "description": "Complete Grafana dashboard JSON object"},
                "message": {"type": "string", "description": "Commit message explaining the changes"},
                "overwrite": {"type": "boolean", "description": "Whether to overwrite existing dashboard with the same UID (default: true)"}
            },
            "required": ["dashboard"]
        },
        "handler": handle_grafana_save_dashboard
    },
    {
        "name": "grafana_sync_dashboard_file",
        "description": "Read a local JSON dashboard file, import/push it to Grafana, and ensure the public share link is active.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to local JSON dashboard file (default: monitoring/grafana/dashboards/ada-overview.json)"},
                "overwrite": {"type": "boolean", "description": "Whether to overwrite in Grafana (default: true)"},
                "message": {"type": "string", "description": "Commit message for Grafana version history"}
            }
        },
        "handler": handle_grafana_sync_dashboard_file
    },
    {
        "name": "grafana_export_dashboard_file",
        "description": "Fetch a live dashboard from Grafana and save/export it directly to a local JSON file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "UID of the dashboard to export (default: ada-overview)"},
                "file_path": {"type": "string", "description": "Destination file path (default: monitoring/grafana/dashboards/ada-overview.json)"}
            }
        },
        "handler": handle_grafana_export_dashboard_file
    },
    {
        "name": "grafana_list_datasources",
        "description": "List all configured datasources (e.g. Prometheus) in Grafana with their UIDs and URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
        "handler": handle_grafana_list_datasources
    },
    {
        "name": "grafana_manage_public_dashboard",
        "description": "Get or generate a public dashboard share token (access without login) for a dashboard UID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dashboard_uid": {"type": "string", "description": "The UID of the dashboard (default: 'ada-overview')"},
                "action": {"type": "string", "enum": ["get", "create", "get_or_create"], "description": "Action to perform (default: 'get_or_create')"}
            }
        },
        "handler": handle_grafana_manage_public_dashboard
    }
]

TOOL_MAP = {t["name"]: t for t in TOOLS}


# =============================================================================
# JSON-RPC 2.0 Protocol Loop
# =============================================================================

def send_response(response: dict):
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main():
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except Exception as e:
            send_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "antigravity-grafana-mcp",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            })
        elif method == "notifications/initialized" or method == "initialized":
            pass
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method == "tools/list":
            tool_list = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"]
                }
                for t in TOOLS
            ]
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": tool_list
                }
            })
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if tool_name not in TOOL_MAP:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
                })
            else:
                try:
                    result_text = TOOL_MAP[tool_name]["handler"](tool_args)
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result_text
                                }
                            ]
                        }
                    })
                except Exception as e:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "isError": True,
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Error executing {tool_name}: {e}"
                                }
                            ]
                        }
                    })
        else:
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                })


if __name__ == "__main__":
    main()
