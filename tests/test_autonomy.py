import tempfile
import unittest
from pathlib import Path

from ada.application.services.autonomy import AutonomyService
from ada.infrastructure.persistence.sqlite import Memory


class AutonomyTests(unittest.TestCase):
    def test_event_rule_proposes_by_default_and_filters_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "memory.db"))

            class FakePlanner:
                def from_actions(self, actions, explanation=""):
                    return type("Plan", (), {"plan_id": "plan-1", "high_risk": lambda self: False})()

            class FakeAgent:
                cfg = {"event_rules": {"files": {"action": "analyze_photo", "extensions": [".jpg"]}}}
                skills = {"analyze_photo": object()}
                planner = FakePlanner()
                mem = memory

            service = AutonomyService(FakeAgent())
            filtered = service.handle("files", {"path": "/tmp/file.txt"})
            proposed = service.handle("files", {"path": "/tmp/file.jpg"})
            self.assertEqual(filtered["status"], "filtered")
            self.assertEqual(proposed["status"], "proposed")

    def test_geofence_and_inventory_filters(self):
        inside = {"coordinates": {"lat": -34.6037, "lon": -58.3816}, "quantity": 1}
        rule = {"geofence": {"lat": -34.6037, "lon": -58.3816, "radius_m": 100}, "inventory_max": 2}
        self.assertTrue(AutonomyService._matches(rule, inside))
        outside = {"coordinates": {"lat": -34.7, "lon": -58.5}, "quantity": 1}
        self.assertFalse(AutonomyService._matches(rule, outside))
        self.assertFalse(AutonomyService._matches(rule, {"coordinates": inside["coordinates"], "quantity": 3}))


if __name__ == "__main__":
    unittest.main()
