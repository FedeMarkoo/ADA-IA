"""Event-to-task bridge for controlled, auditable autonomy."""

import logging
from pathlib import Path

from ada.domain.tasks import Action

logger = logging.getLogger("ada.autonomy")


class AutonomyService:
    def __init__(self, agent, config=None):
        self.agent = agent
        self.config = config or getattr(agent, "cfg", {})

    def handle(self, topic, payload):
        rule = (self.config.get("event_rules") or {}).get(topic)
        if not isinstance(rule, dict) or not rule.get("action"):
            return {"ok": True, "status": "ignored", "topic": topic}
        if not self._matches(rule, payload):
            return {"ok": True, "status": "filtered", "topic": topic}
        action_name = str(rule["action"])
        if action_name not in self.agent.skills:
            return {"ok": False, "error": "configured_action_unavailable", "action": action_name}
        arguments = dict(rule.get("payload") or {})
        if isinstance(payload, dict):
            arguments.setdefault("path", payload.get("path"))
        arguments = {key: value for key, value in arguments.items() if value is not None}
        action = Action(action_name, arguments)
        plan = self.agent.planner.from_actions([action], explanation=f"Regla de evento: {topic}")
        auto_execute = bool(rule.get("auto_execute", False)) and not plan.high_risk()
        task = {
            "type": action_name,
            "payload": arguments,
            "prompt": f"Evento autorizado {topic}",
            "complexity": int(rule.get("complexity", 3)),
            "confirm": bool(rule.get("auto_confirm", False)) if auto_execute else None,
        }
        if not auto_execute:
            result = {"ok": True, "status": "proposed", "plan_id": plan.plan_id, "action": action_name}
        else:
            result = self.agent.decide_and_run(task)
            result = {
                "ok": not bool(result.get("result", {}).get("error")) if isinstance(result, dict) else True,
                "status": "executed",
                "plan_id": plan.plan_id,
                "action": action_name,
                "result": result,
            }
        self.agent.mem.record_audit(topic, request=task, result=result, success=bool(result.get("ok")))
        return result

    @staticmethod
    def _matches(rule, payload):
        extensions = rule.get("extensions") or []
        if not extensions:
            return True
        path = Path(str((payload or {}).get("path", "")))
        return path.suffix.lower() in {
            str(item).lower() if str(item).startswith(".") else f".{str(item).lower()}" for item in extensions
        }
