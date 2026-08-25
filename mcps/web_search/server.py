"""Web Search MCP Server main entry point."""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcps.protocol import StdioMCPServer
from mcps.web_search.searcher import WebSearcher


def create_web_search_server() -> StdioMCPServer:
    server = StdioMCPServer("web-search", "1.1.0")
    searcher = WebSearcher()

    server.register_tool(
        name="web_search.search",
        description="Realiza búsquedas en la web utilizando DuckDuckGo/Brave.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda"},
                "limit": {"type": "integer", "description": "Número máximo de resultados", "default": 5},
            },
            "required": ["query"],
        },
        handler=searcher.search,
        risk_level="safe",
    )

    return server


if __name__ == "__main__":
    srv = create_web_search_server()
    srv.run()
