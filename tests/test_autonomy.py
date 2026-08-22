import unittest
from unittest.mock import MagicMock

from ada.application.services.autonomy import AutonomyService


class TestAutonomyService(unittest.TestCase):
    def setUp(self):
        self.mock_agent = MagicMock()
        self.mock_agent.skills = {"organize_photos": lambda _: {"ok": True}}
        self.config = {
            "event_rules": {
                "filesystem.file_created": {
                    "action": "organize_photos",
                    "path_prefix": "/home/user/Photos",
                    "extensions": [".jpg", ".png"],
                    "auto_execute": False,
                }
            }
        }
        self.service = AutonomyService(self.mock_agent, self.config)

    def test_path_prefix_security(self):
        rule = self.config["event_rules"]["filesystem.file_created"]
        # Legitimate path under prefix
        self.assertTrue(self.service._matches(rule, {"path": "/home/user/Photos/2026/event.jpg"}))
        # Path that shares prefix as string but is a sibling directory (e.g. Photos_evil)
        self.assertFalse(self.service._matches(rule, {"path": "/home/user/Photos_evil/event.jpg"}))
        # Non-matching extension
        self.assertFalse(self.service._matches(rule, {"path": "/home/user/Photos/doc.pdf"}))

    def test_geofence_calculation(self):
        # Center: Obelisco, Buenos Aires (-34.6037, -58.3816)
        geofence = {"lat": -34.6037, "lon": -58.3816, "radius_m": 500}
        # Point ~100m away (Plaza de la República)
        inside_point = {"lat": -34.6033, "lon": -58.3811}
        self.assertTrue(AutonomyService._inside_geofence(inside_point, geofence))

        # Point ~2000m away (Puerto Madero)
        outside_point = {"lat": -34.6150, "lon": -58.3650}
        self.assertFalse(AutonomyService._inside_geofence(outside_point, geofence))

        # Invalid coordinates
        self.assertFalse(AutonomyService._inside_geofence({"lat": "invalid"}, geofence))
        self.assertFalse(AutonomyService._inside_geofence(None, geofence))


if __name__ == "__main__":
    unittest.main()
