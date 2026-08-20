"""MCP tool bridge for explicitly configured local and remote servers."""

from ada.infrastructure.integrations.mcp import MCPClient


def run(args):
    servers = args.get("servers") or args.get("mcpServers") or args.get("mcp_servers") or {}
    name = args.get("server")
    if not servers:
        return {"error": "no_mcp_servers_configured", "message": "Agregá servidores MCP en config.json o .vscode/mcp.json."}
    if name not in servers:
        return {"error": "mcp_server_not_found", "server": name, "available": sorted(servers)}
    server = servers[name]
    if isinstance(server, str):
        server = {"command": server}
    if not isinstance(server, dict):
        return {"error": "invalid_mcp_server_config", "server": name}
    try:
        return MCPClient(server).call(
            tool=args.get("tool"), arguments=args.get("arguments"), list_only=bool(args.get("list_tools"))
        )
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        return {"error": "mcp_execution_failed", "server": name, "message": str(exc)}
