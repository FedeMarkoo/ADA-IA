"""Single source of truth adapter for declarative MCP tools."""

from typing import Any, Dict, Iterable, Optional


class ToolRegistry:
    def __init__(self, mcp_manager=None):
        self.mcp_manager = mcp_manager

    def all(self, category: Optional[str] = None) -> list[Dict[str, Any]]:
        if not self.mcp_manager:
            return []
        tools = self.mcp_manager.list_tools(category=category) if category else self.mcp_manager.list_tools()
        return [tool for tool in tools if tool.get("enabled")]

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        for tool in self.all():
            if tool.get("name") == name:
                return tool
        return None

    def router_catalog(self, category: Optional[str] = None) -> Iterable[str]:
        for tool in self.all(category):
            confirmation = " (requiere confirmación)" if tool.get("requires_confirmation") else ""
            yield f"- {tool.get('name')} [{tool.get('category') or tool.get('server')}] — {tool.get('description') or 'sin descripción'}{confirmation}"
