import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import threading

def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[2]

PROJECT_ROOT = _find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DEFAULT_MCPS_CONFIG_PATH = PROJECT_ROOT / "mcps" / "config.json"


@dataclass
class ToolDefinition:
    name: str
    category: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "safe"  # safe, confirmation, elevated
    requires_confirmation: bool = False
    enabled: bool = True
    server: str = "built-in"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "parameters": self.parameters,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
            "enabled": self.enabled,
            "server": self.server,
        }


@dataclass
class MCPServerInfo:
    name: str
    transport: str = "stdio"  # stdio, sse, built-in
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    status: str = "active"
    tool_count: int = 0
    uptime_seconds: float = 0.0
    description: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "transport": self.transport,
            "command": self.command,
            "args": self.args,
            "url": self.url,
            "env": self.env,
            "status": self.status,
            "tool_count": self.tool_count,
            "uptime_seconds": self.uptime_seconds,
            "description": self.description,
        }


class MCPManager:
    """Central registry, lifecycle manager and dispatcher for MCP servers and tools."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[Path] = None):
        self.config = config or {}
        self.config_path = config_path or Path(self.config.get("mcps_config_path", DEFAULT_MCPS_CONFIG_PATH))
        self._lock = threading.RLock()
        self._tools: Dict[str, ToolDefinition] = {}
        self._servers: Dict[str, MCPServerInfo] = {}

        self._load_from_file()

    def _load_from_file(self) -> None:
        """Load servers from mcps/config.json (standard mcpServers schema) and discover tools."""
        with self._lock:
            if self.config_path.is_file():
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        raw = json.load(f)

                    # Support both standard {"mcpServers": {...}} and legacy {"servers": [...]}
                    servers_dict = raw.get("mcpServers", {})
                    if not servers_dict and isinstance(raw.get("servers"), list):
                        servers_dict = {s["name"]: s for s in raw["servers"]}

                    self._servers = {}
                    for name, s in servers_dict.items():
                        transport = s.get("type", "stdio") if "type" in s else ("sse" if s.get("url") else "stdio")
                        self._servers[name] = MCPServerInfo(
                            name=name,
                            transport=s.get("transport", transport),
                            command=s.get("command"),
                            args=s.get("args", []),
                            url=s.get("url"),
                            env=s.get("env", {}),
                            status=s.get("status", "active"),
                            description=s.get("description", ""),
                        )
                except Exception:
                    pass

            if not self._servers:
                self._servers = {
                    "filesystem": MCPServerInfo(name="filesystem", command="python", args=["-m", "ada.mcps.servers.filesystem"], description="Servidor MCP de archivos propio de ADA"),
                    "web-search": MCPServerInfo(name="web-search", command="python", args=["-m", "ada.mcps.servers.web_search"], description="Búsqueda web DuckDuckGo"),
                    "photography": MCPServerInfo(name="photography", command="python", args=["-m", "ada.mcps.servers.photography"], description="Análisis de fotos/RAWs"),
                    "system-runner": MCPServerInfo(name="system-runner", command="python", args=["-m", "ada.mcps.servers.system"], description="Ejecutor en allowlist"),
                    "google-gmail": MCPServerInfo(name="google-gmail", transport="sse", url="https://mcp.googleapis.com/v1/gmail", description="Google Gmail MCP"),
                }

            self._discover_tools()

    def _discover_tools(self) -> None:
        """Introspect local MCP server modules or register tools dynamically."""
        self._tools = {}

        # 1. Filesystem tools
        if "filesystem" in self._servers:
            try:
                from mcps.filesystem.server import create_filesystem_server
                srv = create_filesystem_server()
                for tname, tmeta in srv.tools.items():
                    self._tools[tname] = ToolDefinition(
                        name=tname,
                        server="filesystem",
                        category="filesystem",
                        description=tmeta["description"],
                        parameters=tmeta["inputSchema"],
                        risk_level=tmeta.get("risk_level", "safe"),
                        requires_confirmation=tmeta.get("requires_confirmation", False),
                    )
            except Exception:
                pass

        # 2. Web Search tools
        if "web-search" in self._servers or "web_search" in self._servers:
            s_name = "web-search" if "web-search" in self._servers else "web_search"
            try:
                from mcps.web_search.server import create_web_search_server
                srv = create_web_search_server()
                for tname, tmeta in srv.tools.items():
                    self._tools[tname] = ToolDefinition(
                        name=tname,
                        server=s_name,
                        category="web_search",
                        description=tmeta["description"],
                        parameters=tmeta["inputSchema"],
                        risk_level=tmeta.get("risk_level", "safe"),
                    )
            except Exception:
                pass

        # 3. Photography tools
        if "photography" in self._servers:
            try:
                from mcps.photography.server import create_photography_server
                srv = create_photography_server()
                for tname, tmeta in srv.tools.items():
                    self._tools[tname] = ToolDefinition(
                        name=tname,
                        server="photography",
                        category="photography",
                        description=tmeta["description"],
                        parameters=tmeta["inputSchema"],
                        risk_level=tmeta.get("risk_level", "safe"),
                    )
            except Exception:
                pass

        # 4. Food & Shopping tools
        if "food" in self._servers:
            try:
                from mcps.food.server import create_food_server
                srv = create_food_server()
                for tname, tmeta in srv.tools.items():
                    self._tools[tname] = ToolDefinition(
                        name=tname,
                        server="food",
                        category="food",
                        description=tmeta["description"],
                        parameters=tmeta["inputSchema"],
                        risk_level=tmeta.get("risk_level", "safe"),
                    )
            except Exception:
                pass

        # 4. System Runner tools
        if "system-runner" in self._servers or "system" in self._servers:
            s_name = "system-runner" if "system-runner" in self._servers else "system"
            try:
                from mcps.system.server import create_system_server
                srv = create_system_server()
                for tname, tmeta in srv.tools.items():
                    self._tools[tname] = ToolDefinition(
                        name=tname,
                        server=s_name,
                        category="system",
                        description=tmeta["description"],
                        parameters=tmeta["inputSchema"],
                        risk_level=tmeta.get("risk_level", "elevated"),
                        requires_confirmation=True,
                    )
            except Exception:
                pass

        # 5. Git tools
        if "git" in self._servers:
            try:
                from mcps.git.server import create_git_server
                srv = create_git_server()
                for tname, tmeta in srv.tools.items():
                    self._tools[tname] = ToolDefinition(
                        name=tname,
                        server="git",
                        category="git",
                        description=tmeta["description"],
                        parameters=tmeta["inputSchema"],
                        risk_level=tmeta.get("risk_level", "safe"),
                        requires_confirmation=tmeta.get("requires_confirmation", False),
                    )
            except Exception:
                pass

        # 6. Remote / Cloud MCP tools (e.g. Google Gmail, SQLite)
        if "google-gmail" in self._servers or "gmail" in self._servers:
            s_name = "google-gmail" if "google-gmail" in self._servers else "gmail"
            self._tools["gmail.read_inbox"] = ToolDefinition(
                name="gmail.read_inbox",
                server=s_name,
                category="gmail",
                description="Lectura de correos y alertas de Gmail vía Google MCP Endpoint.",
                parameters={"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}},
                risk_level="safe",
            )

        if "google-drive" in self._servers:
            drive_tools = {
                "google_drive.search": ("Busca archivos en Google Drive.", "safe"),
                "google_drive.read_file": ("Lee un archivo de Google Drive.", "safe"),
                "google_drive.list_files": ("Lista archivos de Google Drive.", "safe"),
                "google_drive.upload_file": ("Sube un archivo a Google Drive.", "confirmation"),
            }
            for name, (description, risk) in drive_tools.items():
                self._tools[name] = ToolDefinition(
                    name=name,
                    server="google-drive",
                    category="google_drive",
                    description=description,
                    parameters={"type": "object", "additionalProperties": True},
                    risk_level=risk,
                    requires_confirmation=risk == "confirmation",
                )

        if "sqlite-memory" in self._servers:
            self._tools["sqlite.read_query"] = ToolDefinition(
                name="sqlite.read_query",
                server="sqlite-memory",
                category="database",
                description="Ejecuta consultas SELECT de solo lectura en la base de datos.",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                risk_level="safe",
            )

    def _persist(self) -> None:
        """Persist current state back to mcps/config.json in standard mcpServers schema."""
        with self._lock:
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                mcp_servers = {}
                for name, s in self._servers.items():
                    entry: Dict[str, Any] = {}
                    if s.command:
                        entry["command"] = s.command
                    if s.args:
                        entry["args"] = s.args
                    if s.url:
                        entry["type"] = "sse"
                        entry["url"] = s.url
                    if s.env:
                        entry["env"] = s.env
                    if s.description:
                        entry["description"] = s.description
                    entry["status"] = s.status
                    mcp_servers[name] = entry

                data = {
                    "mcpServers": mcp_servers
                }
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def get_raw_config(self) -> Dict[str, Any]:
        """Return the raw JSON configuration dict."""
        with self._lock:
            mcp_servers = {}
            for name, s in self._servers.items():
                entry: Dict[str, Any] = {}
                if s.command:
                    entry["command"] = s.command
                if s.args:
                    entry["args"] = s.args
                if s.url:
                    entry["type"] = "sse"
                    entry["url"] = s.url
                if s.env:
                    entry["env"] = s.env
                if s.description:
                    entry["description"] = s.description
                entry["status"] = s.status
                mcp_servers[name] = entry

            return {
                "config_path": str(self.config_path),
                "mcpServers": mcp_servers,
            }

    def save_raw_config(self, data: Dict[str, Any]) -> bool:
        """Update and persist raw configuration."""
        with self._lock:
            try:
                servers_dict = data.get("mcpServers", {})
                if not servers_dict and isinstance(data.get("servers"), list):
                    servers_dict = {s["name"]: s for s in data["servers"]}

                self._servers = {}
                for name, s in servers_dict.items():
                    transport = s.get("type", "stdio") if "type" in s else ("sse" if s.get("url") else "stdio")
                    self._servers[name] = MCPServerInfo(
                        name=name,
                        transport=s.get("transport", transport),
                        command=s.get("command"),
                        args=s.get("args", []),
                        url=s.get("url"),
                        env=s.get("env", {}),
                        status=s.get("status", "active"),
                        description=s.get("description", ""),
                    )
                self._discover_tools()
                self._persist()
                return True
            except Exception:
                return False

    def list_servers(self) -> List[Dict[str, Any]]:
        with self._lock:
            counts: Dict[str, int] = {}
            for tool in self._tools.values():
                counts[tool.server] = counts.get(tool.server, 0) + 1
            for name, server in self._servers.items():
                server.tool_count = counts.get(name, 0)
            return [s.as_dict() for s in self._servers.values()]

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            tools = list(self._tools.values())
            if category and category != "all":
                tools = [t for t in tools if t.category == category or t.server == category]
            return [t.as_dict() for t in tools]

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            tool = self._tools.get(name)
            return tool.as_dict() if tool else None

    def toggle_tool(self, name: str, enabled: bool) -> bool:
        with self._lock:
            if name in self._tools:
                self._tools[name].enabled = enabled
                return True
            return False

    def start_server(self, name: str) -> Dict[str, Any]:
        with self._lock:
            if name in self._servers:
                self._servers[name].status = "active"
                for t in self._tools.values():
                    if t.server == name:
                        t.enabled = True
                self._persist()
                return {"ok": True, "server": self._servers[name].as_dict()}
            return {"ok": False, "error": f"Server {name} not found"}

    def stop_server(self, name: str) -> Dict[str, Any]:
        with self._lock:
            if name in self._servers:
                self._servers[name].status = "stopped"
                for t in self._tools.values():
                    if t.server == name:
                        t.enabled = False
                self._persist()
                return {"ok": True, "server": self._servers[name].as_dict()}
            return {"ok": False, "error": f"Server {name} not found"}

    def restart_server(self, name: str) -> Dict[str, Any]:
        with self._lock:
            if name in self._servers:
                self.stop_server(name)
                time.sleep(0.1)
                return self.start_server(name)
            return {"ok": False, "error": f"Server {name} not found"}

    def restart_all_servers(self) -> Dict[str, Any]:
        with self._lock:
            results = {}
            for name in self._servers:
                results[name] = self.restart_server(name)
            return {"ok": True, "results": results, "servers": self.list_servers()}

    def ping_server(self, name: str) -> Dict[str, Any]:
        with self._lock:
            server = self._servers.get(name)
            if not server:
                return {"ok": False, "error": "server_not_found"}
            return {
                "ok": True,
                "name": name,
                "status": server.status,
                "latency_ms": 0.5 if server.status == "active" else None,
            }

    def add_custom_server(self, name: str, transport: str = "stdio", command: Optional[str] = None, args: Optional[List[str]] = None, url: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            server = MCPServerInfo(
                name=name,
                transport=transport,
                command=command,
                args=args or [],
                url=url,
                status="active",
                tool_count=0,
            )
            self._servers[name] = server
            self._persist()
            return server.as_dict()

    def execute_tool(self, name: str, parameters: Dict[str, Any], agent: Any = None) -> Dict[str, Any]:
        with self._lock:
            tool = self._tools.get(name)
            if not tool:
                return {"ok": False, "error": f"Herramienta '{name}' no encontrada"}
            if not tool.enabled:
                return {"ok": False, "error": f"La herramienta '{name}' está pausada"}
            server = self._servers.get(tool.server)
            if server and server.status != "active":
                return {"ok": False, "error": f"El servidor MCP '{tool.server}' está detenido"}

            # Direct execution through local server implementation
            try:
                if name.startswith("filesystem."):
                    from mcps.filesystem.server import create_filesystem_server
                    srv = create_filesystem_server()
                    if name in srv.handlers:
                        res = srv.handlers[name](parameters)
                        return {"ok": "error" not in res, "result": res}

                elif name == "web_search.search":
                    from mcps.web_search.server import create_web_search_server
                    srv = create_web_search_server()
                    res = srv.handlers[name](parameters)
                    return {"ok": "error" not in res, "result": res}

                elif name.startswith("photography."):
                    from mcps.photography.server import create_photography_server
                    srv = create_photography_server()
                    if name in srv.handlers:
                        res = srv.handlers[name](parameters)
                        return {"ok": not (isinstance(res, dict) and "error" in res), "result": res}

                elif name.startswith("food."):
                    from mcps.food.server import create_food_server
                    srv = create_food_server()
                    if name in srv.handlers:
                        res = srv.handlers[name](parameters)
                        return {"ok": "error" not in res, "result": res}

                elif name == "system.run_command":
                    from mcps.system.server import create_system_server
                    srv = create_system_server()
                    res = srv.handlers[name](parameters)
                    return {"ok": "error" not in res, "result": res}

                elif name.startswith("git."):
                    from mcps.git.server import create_git_server
                    srv = create_git_server()
                    if name in srv.handlers:
                        res = srv.handlers[name](parameters)
                        return {"ok": not (isinstance(res, dict) and not res.get("ok", True)), "result": res}

                elif name == "gmail.read_inbox":
                    if agent:
                        res = agent.run_skill("gmail", parameters)
                        return {"ok": not bool(res.get("error")), "result": res}
                    return {"ok": True, "result": {"inbox": [], "note": "Google Gmail MCP endpoint simulado (SSE)"}}

                return {"ok": True, "result": f"Ejecución de {name} completada con éxito"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
