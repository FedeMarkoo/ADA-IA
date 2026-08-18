"""MCP tool bridge. Disabled until servers are explicitly configured."""
from src.ada.infrastructure.integrations.mcp import MCPClient


def run(args):
    servers = args.get('servers') or {}
    name = args.get('server')
    if not servers:
        return {'error': 'no_mcp_servers_configured', 'message': 'Agregá un servidor en config.json bajo mcp_servers.'}
    if name not in servers:
        return {'error': 'mcp_server_not_found', 'server': name, 'available': sorted(servers)}
    command = servers[name].get('command') if isinstance(servers[name], dict) else servers[name]
    if not command:
        return {'error': 'invalid_mcp_server_command', 'server': name}
    return MCPClient(command).call(tool=args.get('tool'), arguments=args.get('arguments'), list_only=bool(args.get('list_tools')))
