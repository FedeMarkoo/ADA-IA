import unittest
from unittest.mock import patch

from ada.infrastructure.engines.model_manager import ModelManager
from ada.infrastructure.runtime.ollama import LocalModelRuntime
from ada.infrastructure.runtime.resources import hardware_profile


class RuntimeTests(unittest.TestCase):
    def test_hardware_profile_has_portable_shape(self):
        profile = hardware_profile()
        self.assertIn(profile["tier"], {"low", "mid", "high"})
        self.assertGreaterEqual(profile["cpu_cores"], 1)
        self.assertIn("gpu_backend", profile)
        self.assertIn("disk_free_gb", profile)

    def test_model_policy_can_choose_without_code_changes(self):
        manager = ModelManager(
            {
                "model_catalog": [{"name": "small-model", "min_ram_gb": 0}],
                "model_policy": {"chat": {"preferred": "small-model", "fallbacks": []}},
                "local_runtime": {"auto_start": False},
            }
        )
        self.assertEqual(manager.select_model("chat"), "small-model")
        self.assertEqual(manager.select_model({"type": "chat"}), "small-model")
        self.assertIn("roles", manager.model_recommendations())

    def test_runtime_can_report_missing_service_without_starting(self):
        runtime = LocalModelRuntime(
            {
                "ollama_url": "http://127.0.0.1:1",
                "local_runtime": {"auto_start": False},
            }
        )
        status = runtime.ensure_ready()
        self.assertFalse(status.available)
        self.assertEqual(status.reason, "not_running")

    def test_model_manager_exposes_local_capability_and_runtime(self):
        manager = ModelManager(
            {
                "ollama_url": "http://127.0.0.1:1",
                "local_runtime": {"auto_start": False},
                "engine_priority": ["local", "unknown"],
            }
        )
        available = manager.available()
        self.assertIn("local", available)
        self.assertIn("ollama", available)
        self.assertFalse(available["local"])
        self.assertEqual(manager.choose({"complexity": 3}), None)
        self.assertIn("status", manager.runtime_status())

    def test_adaptive_models_use_observed_latency_and_errors(self):
        manager = ModelManager(
            {
                "adaptive_models": True,
                "model_policy": {"chat": {"preferred": "slow", "fallbacks": ["fast"]}},
                "model_catalog": [{"name": "slow"}, {"name": "fast"}],
            }
        )
        with patch.object(manager, "_call_ollama", return_value="ok"):
            for _ in range(2):
                manager.call("ollama", "test", ollama_model="slow")
            manager._record_model_stat("slow", 10.0, error=True)
            manager._record_model_stat("fast", 0.1)
        self.assertEqual(manager.select_model("chat"), "fast")
        self.assertTrue(manager.model_recommendations()["model_stats"])


if __name__ == "__main__":
    unittest.main()
