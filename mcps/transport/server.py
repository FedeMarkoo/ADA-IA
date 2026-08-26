"""Transport MCP server entry point."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcps.protocol import StdioMCPServer
from mcps.transport.status import run


def create_transport_server() -> StdioMCPServer:
    server = StdioMCPServer("transport", "1.0.0")
    server.register_tool(
        name="transport.get_status",
        description="Consulta el estado y las alertas de una línea de transporte público.",
        parameters={
            "type": "object",
            "properties": {
                "line": {"type": "string", "enum": ["sarmiento"]},
                "station": {"type": "string"},
                "direction": {"type": "string"},
                "config": {"type": "object"},
            },
            "required": ["line"],
            "additionalProperties": False,
        },
        handler=run,
        risk_level="safe",
    )
    return server


if __name__ == "__main__":
    create_transport_server().run()
