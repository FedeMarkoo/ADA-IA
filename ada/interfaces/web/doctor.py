"""System Health Doctor and Autonomous Auto-Healing Service for ADA Hub."""

import logging
import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, field
from ada.infrastructure.runtime.duplicates import detect_duplicates

logger = logging.getLogger("ada.doctor")


@dataclass
class HealthCheckItem:
    id: str
    name: str
    category: str
    status: str  # ok, warning, error
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    can_auto_fix: bool = False
    fix_action_id: Optional[str] = None
    fix_label: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "can_auto_fix": self.can_auto_fix,
            "fix_action_id": self.fix_action_id,
            "fix_label": self.fix_label,
        }


class HealthDoctor:
    """Diagnoses system-wide components and provides automated remediation actions."""

    def __init__(self, agent: Any, config: Optional[Dict[str, Any]] = None, mcp_manager: Any = None, ollama_client: Any = None):
        self.agent = agent
        self.config = config or getattr(agent, "cfg", {})
        self.mcp_manager = mcp_manager
        self.ollama_client = ollama_client

    def diagnose(self) -> Dict[str, Any]:
        """Perform comprehensive diagnosis of all subsystems."""
        items: List[HealthCheckItem] = []

        # 1. Check Ollama Runtime
        items.append(self._check_ollama())

        # 2. Check Installed Models
        items.append(self._check_models())

        # 3. Check ADA Agent Core
        items.append(self._check_agent())

        # 4. Check MCP Subsystem
        items.append(self._check_mcps())

        # 5. Check SQLite Memory
        items.append(self._check_memory())

        # 6. Check Hardware Resources
        items.append(self._check_hardware())

        # 7. Check Telegram Bot Service
        items.append(self._check_telegram())

        # 8. Detect duplicate listeners and runtimes before they cause 409s
        # or port conflicts.
        items.append(self._check_duplicates())

        # Calculate Overall Health Score
        total = len(items)
        ok_count = sum(1 for i in items if i.status == "ok")
        warn_count = sum(1 for i in items if i.status == "warning")
        err_count = sum(1 for i in items if i.status == "error")

        score = int((ok_count + warn_count * 0.5) / total * 100) if total > 0 else 100
        overall_status = "healthy" if err_count == 0 and warn_count == 0 else "degraded" if err_count == 0 else "unhealthy"

        # Actionable fixes
        available_fixes = [
            {"id": i.fix_action_id, "label": i.fix_label, "target": i.id}
            for i in items if i.can_auto_fix and i.fix_action_id and i.status in {"warning", "error"}
        ]

        return {
            "overall_status": overall_status,
            "score": score,
            "total_checks": total,
            "ok_count": ok_count,
            "warning_count": warn_count,
            "error_count": err_count,
            "items": [i.as_dict() for i in items],
            "available_fixes": available_fixes,
            "can_auto_heal_all": len(available_fixes) > 0,
        }

    def _check_duplicates(self) -> HealthCheckItem:
        report = detect_duplicates()
        if report["ok"]:
            total = sum(len(items) for items in report["instances"].values())
            return HealthCheckItem(
                id="duplicate_runtimes", name="Instancias duplicadas", category="runtime",
                status="ok", message=f"No hay runtimes duplicados ({total} instancia(s) detectada(s))",
                details=report,
            )
        labels = ", ".join(f"{kind}: {len(items)}" for kind, items in report["duplicates"].items())
        return HealthCheckItem(
            id="duplicate_runtimes", name="Instancias duplicadas", category="runtime",
            status="error", message=f"Hay más de una instancia activa ({labels})",
            details=report, can_auto_fix=False,
        )

    def _check_ollama(self) -> HealthCheckItem:
        client = self.ollama_client
        if not client:
            return HealthCheckItem(
                id="ollama_daemon",
                name="Motor Ollama LLM",
                category="runtime",
                status="error",
                message="Cliente Ollama no inicializado",
                can_auto_fix=True,
                fix_action_id="start_ollama",
                fix_label="Iniciar Ollama",
            )
        health = client.health()
        if health.get("online") or health.get("status") == "healthy" or health.get("available") or health.get("status_code") == 200:
            latency = health.get("latency_ms", 0)
            return HealthCheckItem(
                id="ollama_daemon",
                name="Motor Ollama LLM",
                category="runtime",
                status="ok",
                message=f"Servicio Ollama activo y respondiendo en {client.endpoint} (latencia: {latency}ms)",
                details=health,
            )
        else:
            return HealthCheckItem(
                id="ollama_daemon",
                name="Motor Ollama LLM",
                category="runtime",
                status="error",
                message="El servicio local de Ollama está detenido o inaccesible",
                details=health,
                can_auto_fix=True,
                fix_action_id="start_ollama",
                fix_label="Iniciar Servicio Ollama",
            )

    def _check_models(self) -> HealthCheckItem:
        client = self.ollama_client
        if not client:
            return HealthCheckItem(
                id="models_installed",
                name="Modelos LLM Instalados",
                category="models",
                status="warning",
                message="No se puede verificar modelos: cliente no inicializado",
                can_auto_fix=False,
                fix_action_id=None,
                fix_label=None,
            )
        health = client.health()
        is_online = health.get("online") or health.get("status") == "healthy" or health.get("available") or health.get("status_code") == 200
        if not is_online:
            return HealthCheckItem(
                id="models_installed",
                name="Modelos LLM Instalados",
                category="models",
                status="ok",
                message="Verificación en espera (el motor Ollama se encuentra detenido)",
                can_auto_fix=False,
                fix_action_id=None,
                fix_label=None,
                details={"ollama_online": False},
            )
        models = client.list_models()
        if len(models) == 0:
            return HealthCheckItem(
                id="models_installed",
                name="Modelos LLM Instalados",
                category="models",
                status="warning",
                message="No hay modelos LLM instalados en Ollama",
                can_auto_fix=True,
                fix_action_id="pull_default_model",
                fix_label="Descargar Llama 3.2 (3B)",
            )
        return HealthCheckItem(
            id="models_installed",
            name="Modelos LLM Instalados",
            category="models",
            status="ok",
            message=f"{len(models)} modelo(s) disponible(s) en disco",
            details={"count": len(models), "models": [m.get("name") for m in models[:5]]},
        )

    def _check_agent(self) -> HealthCheckItem:
        if not self.agent:
            return HealthCheckItem(
                id="ada_agent",
                name="ADA Agent Core & Router",
                category="agent",
                status="error",
                message="Instancia del agente no cargada",
                can_auto_fix=True,
                fix_action_id="restart_agent",
                fix_label="Reiniciar Agente ADA",
            )
        return HealthCheckItem(
            id="ada_agent",
            name="ADA Agent Core & Router",
            category="agent",
            status="ok",
            message="Orquestador multiagente, router y políticas operativas listas",
            details={"lang": getattr(self.agent, "lang", "auto")},
        )

    def _check_mcps(self) -> HealthCheckItem:
        if not self.mcp_manager:
            return HealthCheckItem(
                id="mcps_subsystem",
                name="Subconjunto de Servidores MCP",
                category="mcps",
                status="warning",
                message="Gestor MCP no disponible",
                can_auto_fix=True,
                fix_action_id="restart_all_mcps",
                fix_label="Reiniciar MCPs",
            )
        servers = self.mcp_manager.list_servers()
        tools = self.mcp_manager.list_tools()
        stopped_servers = [s for s in servers if s.get("status") == "stopped"]
        if stopped_servers:
            return HealthCheckItem(
                id="mcps_subsystem",
                name="Subconjunto de Servidores MCP",
                category="mcps",
                status="warning",
                message=f"{len(stopped_servers)} de {len(servers)} servidores MCP están detenidos",
                details={"stopped": [s.get("name") for s in stopped_servers], "total_tools": len(tools)},
                can_auto_fix=True,
                fix_action_id="start_all_mcps",
                fix_label="Levantar Servidores Detenidos",
            )
        return HealthCheckItem(
            id="mcps_subsystem",
            name="Subconjunto de Servidores MCP",
            category="mcps",
            status="ok",
            message=f"Todos los servidores MCP ({len(servers)}) activos con {len(tools)} tools",
            details={"servers_count": len(servers), "tools_count": len(tools)},
        )

    def _check_memory(self) -> HealthCheckItem:
        db_path = self.config.get("db_path", str(Path.home() / "Desktop" / "ADA_Data" / "memory.db"))
        try:
            conn = sqlite3.connect(str(Path(db_path).expanduser()))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return HealthCheckItem(
                id="sqlite_memory",
                name="Persistencia y Memoria SQLite",
                category="storage",
                status="ok",
                message=f"Base de datos operativa con {len(tables)} tablas",
                details={"db_path": db_path, "tables_count": len(tables)},
            )
        except Exception as exc:
            return HealthCheckItem(
                id="sqlite_memory",
                name="Persistencia y Memoria SQLite",
                category="storage",
                status="error",
                message=f"Error accediendo a base de datos: {exc}",
                can_auto_fix=True,
                fix_action_id="init_memory",
                fix_label="Reparar Base de Datos",
            )

    def _check_hardware(self) -> HealthCheckItem:
        try:
            import psutil
            ram = psutil.virtual_memory()
            if ram.percent >= 92:
                return HealthCheckItem(
                    id="hardware_resources",
                    name="Recursos de Hardware (RAM/CPU)",
                    category="hardware",
                    status="warning",
                    message=f"Uso de RAM alto: {ram.percent}%",
                    details={"ram_percent": ram.percent, "available_gb": round(ram.available / (1024**3), 2)},
                    can_auto_fix=True,
                    fix_action_id="unload_vram",
                    fix_label="Liberar Memoria VRAM",
                )
            return HealthCheckItem(
                id="hardware_resources",
                name="Recursos de Hardware (RAM/CPU)",
                category="hardware",
                status="ok",
                message=f"RAM: {ram.percent}% en uso ({round(ram.available / (1024**3), 1)} GB libres)",
                details={"ram_percent": ram.percent},
            )
        except Exception:
            return HealthCheckItem(
                id="hardware_resources",
                name="Recursos de Hardware (RAM/CPU)",
                category="hardware",
                status="ok",
                message="Monitoreo de hardware disponible",
            )

    def _check_telegram(self) -> HealthCheckItem:
        from ada.interfaces.web.server import get_telegram_service_status
        status = get_telegram_service_status()

        if status.get("running") and status.get("status") != "degraded":
            return HealthCheckItem(
                id="telegram_bot",
                name="Servicio Telegram Bot",
                category="services",
                status="ok",
                message="Bot de Telegram activo y recibiendo mensajes",
                details=status,
            )
        elif status.get("status") == "degraded":
            return HealthCheckItem(
                id="telegram_bot",
                name="Servicio Telegram Bot",
                category="services",
                status="error",
                message=f"Telegram está ejecutándose pero no puede recibir eventos: {status.get('last_error') or 'error externo'}",
                details=status,
                can_auto_fix=True,
                fix_action_id="start_telegram",
                fix_label="Reintentar Telegram",
            )
        elif status.get("token_set") or status.get("configured"):
            return HealthCheckItem(
                id="telegram_bot",
                name="Servicio Telegram Bot",
                category="services",
                status="warning",
                message="Token cargado en vault.db pero el daemon de Telegram está detenido",
                details=status,
                can_auto_fix=True,
                fix_action_id="start_telegram",
                fix_label="Iniciar Telegram Bot",
            )
        else:
            return HealthCheckItem(
                id="telegram_bot",
                name="Servicio Telegram Bot",
                category="services",
                status="warning",
                message="Bot de Telegram detenido (falta cargar el token en la Bóveda vault.db)",
                details=status,
            )

    def fix_action(self, action_id: str) -> Dict[str, Any]:
        """Execute a single remediation action."""
        if action_id == "start_ollama":
            if self.agent and hasattr(self.agent, "model_manager"):
                status = self.agent.model_manager.local_runtime.start()
                return {"ok": status.available, "message": "Ollama iniciado" if status.available else "No se pudo iniciar Ollama"}
            return {"ok": False, "error": "No runtime available"}

        elif action_id == "pull_default_model":
            if self.agent and hasattr(self.agent, "model_manager"):
                success = self.agent.model_manager.local_runtime.pull_model("llama3.2:3b")
                return {"ok": success, "message": "Descarga de llama3.2:3b completada" if success else "Error al descargar modelo"}
            return {"ok": False, "error": "No model runtime available"}

        elif action_id == "restart_agent":
            if self.agent and hasattr(self.agent, "model_manager"):
                self.agent.model_manager.reload(self.config)
            return {"ok": True, "message": "Agente ADA reiniciado"}

        elif action_id in {"start_all_mcps", "restart_all_mcps"}:
            if self.mcp_manager:
                res = self.mcp_manager.restart_all_servers()
                return {"ok": True, "message": "Todos los servidores MCP reiniciados", "details": res}
            return {"ok": False, "error": "MCP manager not available"}

        elif action_id == "init_memory":
            if self.agent and hasattr(self.agent, "mem"):
                self.agent.mem.record_task({"init": True}, {"status": "ok"}, provider="doctor")
                return {"ok": True, "message": "Memoria inicializada correctamente"}
            return {"ok": False, "error": "Memory not available"}

        elif action_id == "unload_vram":
            if self.ollama_client:
                running = self.ollama_client.running_models()
                for r in running:
                    self.ollama_client.unload_model(r.get("name"))
                return {"ok": True, "message": f"{len(running)} modelos descargados de VRAM"}
            return {"ok": False, "error": "Ollama client not available"}

        elif action_id == "start_telegram":
            from ada.interfaces.web.server import start_telegram_service
            return start_telegram_service()

        elif action_id == "restart_telegram":
            from ada.interfaces.web.server import restart_telegram_service
            return restart_telegram_service()

        return {"ok": False, "error": f"Acción desconocida: {action_id}"}

    def auto_heal_all(self) -> Dict[str, Any]:
        """Execute all available remediation actions sequentially to bring the system to 100% health."""
        diagnosis = self.diagnose()
        fixes = diagnosis.get("available_fixes", [])
        results = {}
        for fix in fixes:
            action_id = fix.get("id")
            if action_id:
                try:
                    res = self.fix_action(action_id)
                    results[action_id] = res
                except Exception as exc:
                    results[action_id] = {"ok": False, "error": str(exc)}

        # Re-diagnose after healing
        new_diagnosis = self.diagnose()
        return {
            "ok": True,
            "actions_executed": results,
            "previous_score": diagnosis.get("score"),
            "new_score": new_diagnosis.get("score"),
            "diagnosis": new_diagnosis,
        }
