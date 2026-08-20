"""Event-to-task bridge for controlled, auditable autonomy."""

import logging
import math
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
        payload = payload or {}
        extensions = rule.get("extensions") or []
        if extensions:
            path = Path(str(payload.get("path", "")))
            allowed = {
                str(item).lower() if str(item).startswith(".") else f".{str(item).lower()}" for item in extensions
            }
            if path.suffix.lower() not in allowed:
                return False
        prefix = rule.get("path_prefix")
        if prefix and not str(payload.get("path", "")).startswith(str(prefix)):
            return False
        expected_event = rule.get("event_value")
        if expected_event is not None and payload.get("value") != expected_event:
            return False
        required_location = rule.get("location")
        if required_location and payload.get("location") != required_location:
            return False
        geofence = rule.get("geofence")
        if geofence:
            if not AutonomyService._inside_geofence(payload.get("coordinates"), geofence):
                return False
        inventory_max = rule.get("inventory_max")
        if inventory_max is not None:
            quantity = payload.get("quantity")
            try:
                if quantity is None or float(quantity) > float(inventory_max):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _inside_geofence(coordinates, geofence):
        """Match GPS coordinates against a circular rule without a GIS dependency."""
        if not isinstance(coordinates, dict) or not isinstance(geofence, dict):
            return False
        try:
            lat = float(coordinates["lat"])
            lon = float(coordinates["lon"])
            center_lat = float(geofence["lat"])
            center_lon = float(geofence["lon"])
            radius = float(geofence.get("radius_m", 100))
        except (KeyError, TypeError, ValueError):
            return False
        earth_radius_m = 6_371_000
        lat1, lat2 = math.radians(lat), math.radians(center_lat)
        dlat = lat2 - lat1
        dlon = math.radians(center_lon - lon)
        haversine = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance = 2 * earth_radius_m * math.asin(math.sqrt(haversine))
        return distance <= max(0, radius)
