"""Scheduled transport status notification guarded by explicit presence."""

from __future__ import annotations


from ada.infrastructure.runtime.presence import PresenceStore


class TransportTelegramAlert:
    def __init__(self, agent, send_message, config=None):
        self.agent = agent
        self.send_message = send_message
        self.config = config or getattr(agent, "cfg", {})
        self.presence = PresenceStore(self.config.get("presence_path"))

    def run_once(self, now=None):
        cfg = (self.config.get("triggers") or {}).get("cron", {}).get("sarmiento_status") or {}
        required = str(cfg.get("required_location") or "work")
        presence = self.presence.get(required)
        if not presence.get("active"):
            return {"ok": True, "status": "presence_inactive", "presence": presence}
        manager = getattr(self.agent, "mcp_manager", None)
        if manager is None:
            return {"ok": False, "status": "missing_transport_mcp", "error": "missing_transport_mcp"}
        result = manager.execute_tool(
            "transport.get_status",
            {"line": "sarmiento", "config": self.config},
            self.agent,
        )
        if isinstance(result, dict) and result.get("ok") and isinstance(result.get("result"), dict):
            result = result["result"]
        if isinstance(result, dict):
            text = result.get("message") or "Estado del Sarmiento disponible para revisar."
            alerts = result.get("alerts") or []
            if alerts:
                text += "\n\n" + "\n".join(f"• {item.get('title')}: {item.get('description')}" for item in alerts)
            status = result.get("status", "unknown")
        else:
            text, status = str(result), "unknown"
        chat_id = cfg.get("chat_id")
        if not chat_id:
            return {"ok": False, "status": "chat_id_missing", "result": result}
        self.send_message(str(chat_id), text)
        return {"ok": True, "status": status, "chat_id": str(chat_id), "result": result}
