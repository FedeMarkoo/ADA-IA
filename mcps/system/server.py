"""System Runner MCP Server main entry point."""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcps.protocol import StdioMCPServer
from mcps.system.runner import SystemRunner


def create_system_server() -> StdioMCPServer:
    server = StdioMCPServer("system-runner", "1.0.0")
    runner = SystemRunner()

    server.register_tool(
        name="system.run_command",
        description="Ejecuta un script o comando de sistema autorizado en la allowlist.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Comando seguro a ejecutar"}
            },
            "required": ["command"],
        },
        handler=runner.run_command,
        risk_level="elevated",
        requires_confirmation=True,
    )

    return server


if __name__ == "__main__":
    srv = create_system_server()
    srv.run()
