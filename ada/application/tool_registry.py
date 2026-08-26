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

    @staticmethod
    def validate_parameters(tool: Dict[str, Any], parameters: Optional[Dict[str, Any]]) -> bool:
        schema = tool.get("parameters") or tool.get("inputSchema") or {}
        values = parameters or {}
        if not isinstance(values, dict):
            return False
        required = schema.get("required") or []
        if any(name not in values for name in required):
            return False
        properties = schema.get("properties") or {}
        for name, value in values.items():
            definition = properties.get(name) or {}
            expected = definition.get("type")
            if expected == "string" and not isinstance(value, str):
                return False
            if expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
                return False
            if expected == "boolean" and not isinstance(value, bool):
                return False
            if expected == "array" and not isinstance(value, list):
                return False
        return True
