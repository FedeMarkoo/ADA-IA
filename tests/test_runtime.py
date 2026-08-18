import unittest

from models import ModelManager
from runtime import LocalModelRuntime


class RuntimeTests(unittest.TestCase):
    def test_runtime_can_report_missing_service_without_starting(self):
        runtime = LocalModelRuntime({
            "ollama_url": "http://127.0.0.1:1",
            "local_runtime": {"auto_start": False},
        })
        status = runtime.ensure_ready()
        self.assertFalse(status.available)
        self.assertEqual(status.reason, "not_running")

    def test_model_manager_exposes_local_capability_and_runtime(self):
        manager = ModelManager({
            "ollama_url": "http://127.0.0.1:1",
            "local_runtime": {"auto_start": False},
            "engine_priority": ["local", "unknown"],
        })
        available = manager.available()
        self.assertIn("local", available)
        self.assertIn("ollama", available)
        self.assertFalse(available["local"])
        self.assertEqual(manager.choose({"complexity": 3}), None)
        self.assertIn("status", manager.runtime_status())


if __name__ == "__main__":
    unittest.main()
