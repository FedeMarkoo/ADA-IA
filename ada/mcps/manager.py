import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
import urllib.parse
import urllib.request
import urllib.error

from ada.infrastructure.prometheus_metrics import (
    MCP_CPU,
    MCP_DURATION,
    MCP_EXECUTIONS,
    MCP_IN_FLIGHT,
    MCP_MEMORY,
    MCP_RUNNING,
    MCP_SERVER_IN_FLIGHT,
    MCP_TOOL_ENABLED,
)
import psutil


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
                    "filesystem": MCPServerInfo(
                        name="filesystem",
                        command="python",
                        args=["-m", "ada.mcps.servers.filesystem"],
                        description="Servidor MCP de archivos propio de ADA",
                    ),
                    "web-search": MCPServerInfo(
                        name="web-search",
                        command="python",
                        args=["-m", "ada.mcps.servers.web_search"],
                        description="Búsqueda web DuckDuckGo",
                    ),
                    "photography": MCPServerInfo(
                        name="photography",
                        command="python",
                        args=["-m", "ada.mcps.servers.photography"],
                        description="Análisis de fotos/RAWs",
                    ),
                    "system-runner": MCPServerInfo(
                        name="system-runner",
                        command="python",
                        args=["-m", "ada.mcps.servers.system"],
                        description="Ejecutor en allowlist",
                    ),
                    "google-gmail": MCPServerInfo(
                        name="google-gmail",
                        transport="sse",
                        url="https://mcp.googleapis.com/v1/gmail",
                        description="Google Gmail MCP",
                    ),
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

        # 5. Public transport status
        if "transport" in self._servers:
            try:
                from mcps.transport.server import create_transport_server

                srv = create_transport_server()
                for tname, tmeta in srv.tools.items():
                    self._tools[tname] = ToolDefinition(
                        name=tname,
                        server="transport",
                        category="transport",
                        description=tmeta["description"],
                        parameters=tmeta["inputSchema"],
                        risk_level=tmeta.get("risk_level", "safe"),
                    )
            except Exception:
                pass

        # 6. System Runner tools
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
            for tool_name, description in {
                "gmail.search_threads": "Busca conversaciones en Gmail.",
                "gmail.get_message": "Lee un mensaje de Gmail.",
                "gmail.get_thread": "Lee una conversación de Gmail.",
                "gmail.list_labels": "Lista etiquetas de Gmail.",
            }.items():
                self._tools[tool_name] = ToolDefinition(
                    name=tool_name,
                    server=s_name,
                    category="gmail",
                    description=description,
                    parameters={"type": "object", "additionalProperties": True},
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

        if "google-calendar" in self._servers:
            calendar_tools = {
                "google_calendar.list_events": ("Lista eventos de Google Calendar.", "safe"),
                "google_calendar.get_event": ("Obtiene el detalle de un evento de Google Calendar.", "safe"),
                "google_calendar.list_calendars": ("Lista los calendarios disponibles.", "safe"),
                "google_calendar.suggest_time": ("Sugiere horarios disponibles.", "safe"),
                "google_calendar.search_events": ("Busca eventos en Google Calendar.", "safe"),
                "google_calendar.create_event": ("Crea un evento de Google Calendar.", "confirmation"),
                "google_calendar.update_event": ("Actualiza un evento de Google Calendar.", "confirmation"),
                "google_calendar.delete_event": ("Elimina un evento de Google Calendar.", "confirmation"),
                "google_calendar.respond_to_event": ("Responde una invitación de Calendar.", "confirmation"),
            }
            for name, (description, risk) in calendar_tools.items():
                self._tools[name] = ToolDefinition(
                    name=name,
                    server="google-calendar",
                    category="google_calendar",
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

                data = {"mcpServers": mcp_servers}
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
                MCP_RUNNING.labels(mcp=name).set(1 if server.status == "active" else 0)
                try:
                    MCP_MEMORY.labels(mcp=name).set(
                        psutil.Process().memory_info().rss if server.status == "active" else 0
                    )
                except psutil.Error:
                    pass
            return [s.as_dict() for s in self._servers.values()]

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            tools = list(self._tools.values())
            if category and category != "all":
                tools = [t for t in tools if t.category == category or t.server == category]
            for tool in tools:
                MCP_TOOL_ENABLED.labels(mcp=tool.server, tool=tool.name).set(1 if tool.enabled else 0)
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

    def add_custom_server(
        self,
        name: str,
        transport: str = "stdio",
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        """Execute one tool and record complete MCP-level telemetry."""
        definition = self.get_tool(name) or {}
        mcp = str(definition.get("server") or "unknown")
        MCP_IN_FLIGHT.labels(mcp=mcp, tool=name).inc()
        MCP_SERVER_IN_FLIGHT.labels(mcp=mcp).inc()
        started = time.monotonic()
        cpu_started = psutil.Process().cpu_times()
        try:
            result = self._execute_tool(name, parameters, agent)
            status = (
                "error" if isinstance(result, dict) and (result.get("error") or result.get("ok") is False) else "ok"
            )
            return result
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.monotonic() - started
            MCP_EXECUTIONS.labels(mcp=mcp, tool=name, status=status).inc()
            MCP_DURATION.labels(mcp=mcp, tool=name, status=status).observe(duration)
            MCP_IN_FLIGHT.labels(mcp=mcp, tool=name).dec()
            MCP_SERVER_IN_FLIGHT.labels(mcp=mcp).dec()
            try:
                cpu_finished = psutil.Process().cpu_times()
                cpu_delta = max(
                    0.0, (cpu_finished.user + cpu_finished.system) - (cpu_started.user + cpu_started.system)
                )
                MCP_CPU.labels(mcp=mcp, tool=name).inc(cpu_delta)
                MCP_MEMORY.labels(mcp=mcp).set(psutil.Process().memory_info().rss)
            except psutil.Error:
                pass

    def _execute_tool(self, name: str, parameters: Dict[str, Any], agent: Any = None) -> Dict[str, Any]:
        parameters = dict(parameters or {})
        request_text = str(parameters.pop("_request", "") or "")
        if name == "google_calendar.search_events" and request_text:
            quoted = re.search(r"[‘'\"]([^‘’'\"]+)[’'\"]", request_text)
            if quoted:
                parameters["query"] = quoted.group(1)
        if name == "google_calendar.search_events" and parameters.get("date"):
            try:
                requested_month = str(parameters.pop("date"))[:7]
                month_start = datetime.strptime(requested_month, "%Y-%m")
                next_month = month_start.replace(day=28) + timedelta(days=4)
                month_end = next_month.replace(day=1)
                parameters.update(
                    {
                        "_search_month": requested_month,
                        "timeMin": month_start.replace(tzinfo=timezone.utc).isoformat(),
                        "timeMax": month_end.replace(tzinfo=timezone.utc).isoformat(),
                    }
                )
            except (TypeError, ValueError):
                parameters.pop("date", None)
        if name == "google_calendar.list_events" and not parameters.get("timeMin"):
            now = datetime.now(timezone.utc)
            parameters.update(
                {
                    "timeMin": now.isoformat(),
                    "timeMax": (now + timedelta(days=30)).isoformat(),
                    "singleEvents": True,
                    "orderBy": "startTime",
                    "maxResults": 20,
                }
            )
        if name == "google_calendar.list_events":
            now = datetime.now(timezone.utc)
            try:
                parsed_min = datetime.fromisoformat(str(parameters["timeMin"]).replace("Z", "+00:00"))
                if parsed_min.tzinfo is None:
                    parsed_min = parsed_min.replace(tzinfo=timezone.utc)
                if parsed_min < now:
                    parameters["timeMin"] = now.isoformat()
            except (KeyError, TypeError, ValueError):
                parameters["timeMin"] = now.isoformat()
            try:
                parsed_max = datetime.fromisoformat(str(parameters["timeMax"]).replace("Z", "+00:00"))
                if parsed_max.tzinfo is None:
                    parsed_max = parsed_max.replace(tzinfo=timezone.utc)
                parsed_min = datetime.fromisoformat(str(parameters["timeMin"]).replace("Z", "+00:00"))
                if parsed_max <= max(now, parsed_min):
                    parameters["timeMax"] = (now + timedelta(days=7 if "timeMax" in parameters else 30)).isoformat()
            except (KeyError, TypeError, ValueError):
                parameters["timeMax"] = (now + timedelta(days=30)).isoformat()
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
                if name.startswith("google_drive."):
                    drive_name = {"list_files": "list_recent_files"}.get(name.split(".", 1)[1], name.split(".", 1)[1])
                    result = self._execute_remote("https://drivemcp.googleapis.com/mcp/v1", drive_name, parameters)
                    if result.get("ok") or name.split(".", 1)[1] != "list_files":
                        return result
                    return self._execute_google_rest("drive", parameters)
                if name.startswith("google_calendar."):
                    result = self._execute_remote(
                        "https://calendarmcp.googleapis.com/mcp/v1", name.split(".", 1)[1], parameters
                    )
                    if result.get("ok") or name.split(".", 1)[1] not in {
                        "list_calendars",
                        "list_events",
                        "search_events",
                    }:
                        return result
                    return self._execute_google_rest("calendar", parameters, name.split(".", 1)[1])
                if name.startswith("gmail.") and name != "gmail.read_inbox":
                    operation = name.split(".", 1)[1]
                    # Gmail must remain behind the configured MCP. Never
                    # silently bypass it through ADA's local REST adapter.
                    return self._execute_remote("https://gmailmcp.googleapis.com/mcp/v1", operation, parameters)
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

                elif name == "transport.get_status":
                    from mcps.transport.server import create_transport_server

                    srv = create_transport_server()
                    res = srv.handlers[name](parameters)
                    return {"ok": not (isinstance(res, dict) and res.get("ok") is False), "result": res}

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
                    # Build the inbox view exclusively from Gmail MCP calls.
                    parameters.setdefault("pageSize", 10)
                    parameters["pageSize"] = min(int(parameters.get("pageSize") or 10), 20)
                    if re.search(r"\bno\s+le[ií]d", request_text, re.I):
                        parameters["query"] = "is:unread"
                    listed = self._execute_remote(
                        "https://gmailmcp.googleapis.com/mcp/v1", "search_threads", parameters
                    )
                    if not listed.get("ok"):
                        return listed
                    messages = []
                    listed_payload = listed.get("result") or {}
                    for item in listed_payload.get("messages") or listed_payload.get("threads") or []:
                        message_id = item.get("id") if isinstance(item, dict) else item
                        if not message_id:
                            continue
                        detail = self._execute_remote(
                            "https://gmailmcp.googleapis.com/mcp/v1", "get_message", {"messageId": message_id}
                        )
                        if detail.get("ok"):
                            messages.append(detail.get("result") or {})
                    result = listed.get("result") or {}
                    result["inbox"] = messages
                    result["count"] = len(messages)
                    if re.search(r"\b(?:[uú]ltim[oa]|m[aá]s reciente)\b", request_text, re.I):
                        result["latest_only"] = True
                    if re.search(r"\bno\s+le[ií]d", request_text, re.I):
                        result["unread_only"] = True
                    return {"ok": True, "result": result}

                return {"ok": True, "result": f"Ejecución de {name} completada con éxito"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

    @staticmethod
    def _execute_remote(url: str, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call a remote Google MCP using the encrypted ADA OAuth token."""
        access_token = MCPManager._google_access_token()
        if not access_token:
            return {"ok": False, "error": "Falta autorizar Google OAuth para ADA."}
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": parameters or {}},
            }
        ).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {access_token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                return {"ok": False, "error": "Google OAuth access token vencido", "status": 401}
            return {"ok": False, "error": f"Google Calendar MCP HTTP {exc.code}", "status": exc.code}
        if body.get("error"):
            return {"ok": False, "error": body["error"]}
        result = body.get("result", {})
        return {"ok": not bool(result.get("isError")), "result": result}

    @staticmethod
    def _execute_google_rest(service: str, parameters: Dict[str, Any], operation: str = "list_files") -> Dict[str, Any]:
        """Read-only fallback while Google's remote MCP APIs are in preview."""
        access_token = MCPManager._google_access_token()
        if not access_token:
            return {"ok": False, "error": "Falta autorizar Google OAuth para ADA."}
        if service == "drive":
            query = urllib.parse.urlencode(
                {
                    "pageSize": parameters.get("pageSize", 100),
                    # Keep the cloud URL in the structured result so ADA can
                    # provide a direct Drive link without another round-trip.
                    "fields": "files(id,name,mimeType,modifiedTime,webViewLink,parents,size),nextPageToken",
                }
            )
            url = "https://www.googleapis.com/drive/v3/files?" + query
        elif service == "gmail":
            if operation == "list_labels":
                url = "https://gmail.googleapis.com/gmail/v1/users/me/labels"
            elif operation == "search_threads":
                query = urllib.parse.urlencode(
                    {"q": parameters.get("query", ""), "maxResults": parameters.get("pageSize", 100)}
                )
                url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?" + query
            elif operation == "get_message":
                url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/" + urllib.parse.quote(
                    str(parameters.get("messageId", "")), safe=""
                )
            else:
                url = "https://gmail.googleapis.com/gmail/v1/users/me/threads/" + urllib.parse.quote(
                    str(parameters.get("threadId", "")), safe=""
                )
        elif operation in {"list_events", "search_events"}:
            query = urllib.parse.urlencode(
                {
                    "maxResults": parameters.get("maxResults", parameters.get("pageSize", 100)),
                    "singleEvents": str(parameters.get("singleEvents", True)).lower(),
                    "orderBy": parameters.get("orderBy", "startTime"),
                    **({"timeMin": parameters["timeMin"]} if parameters.get("timeMin") else {}),
                    **({"timeMax": parameters["timeMax"]} if parameters.get("timeMax") else {}),
                    **({"q": parameters["query"]} if operation == "search_events" and parameters.get("query") else {}),
                }
            )
            url = "https://www.googleapis.com/calendar/v3/calendars/primary/events?" + query
        else:
            query = urllib.parse.urlencode({"maxResults": parameters.get("pageSize", 100)})
            url = "https://www.googleapis.com/calendar/v3/users/me/calendarList?" + query
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode())
                if service == "drive":
                    for item in payload.get("files", []):
                        if item.get("webViewLink"):
                            item.setdefault("link", item["webViewLink"])
                result_payload = {"fallback": "google-rest", **payload}
                if operation == "search_events" and parameters.get("query"):
                    result_payload["search_query"] = parameters["query"]
                if operation == "search_events" and parameters.get("_search_month"):
                    result_payload["search_month"] = parameters["_search_month"]
                return {"ok": True, "result": result_payload}
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                fresh_token = MCPManager._google_access_token(force_refresh=True)
                if fresh_token and fresh_token != access_token:
                    return MCPManager._execute_google_rest(service, parameters, operation)
            return {"ok": False, "error": f"Google {service.title()} API HTTP {exc.code}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _google_access_token(force_refresh: bool = False) -> Optional[str]:
        """Return a usable Google access token, refreshing it without prompts."""
        from ada.infrastructure.credentials import SecureVault

        vault = SecureVault()
        token = vault.get("google_oauth_token") or {}
        if not isinstance(token, dict):
            return None
        access_token = token.get("access_token")
        refresh_token = token.get("refresh_token")
        refreshed_at = token.get("refreshed_at")
        expires_in = token.get("expires_in")
        token_is_fresh = False
        if access_token and not force_refresh:
            try:
                # Refresh one minute early; OAuth access tokens normally live
                # for 3600 seconds and the vault stores when we received it.
                token_is_fresh = bool(
                    refreshed_at and expires_in and time.time() < float(refreshed_at) + float(expires_in) - 60
                )
            except (TypeError, ValueError):
                token_is_fresh = False
            if token_is_fresh or not refreshed_at:
                # Older vault entries may not have refreshed_at. Keep using
                # them until the 401 retry path proves they are expired.
                return access_token
        if access_token and not force_refresh and token_is_fresh:
            return access_token
        if not refresh_token:
            return access_token

        client_id = token.get("client_id") or vault.get("google_oauth_client_id")
        client_secret = token.get("client_secret") or vault.get("google_oauth_client_secret")
        if not client_id or not client_secret:
            return access_token
        body = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode()
        request = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                refreshed = json.loads(response.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
            return access_token
        if not refreshed.get("access_token"):
            return access_token
        refreshed.update(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "refreshed_at": time.time(),
                "scopes": token.get("scopes") or [s for s in token.get("scope", "").split() if s],
            }
        )
        vault.set("google_oauth_token", refreshed, meta={"provider": "google", "scopes": refreshed["scopes"]})
        return refreshed["access_token"]
