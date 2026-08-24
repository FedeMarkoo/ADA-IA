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

    def test_runtime_reload_updates_endpoint(self):
        runtime = LocalModelRuntime({"ollama_url": "http://127.0.0.1:1", "local_runtime": {"auto_start": False}})
        runtime.reload({"ollama_url": "http://127.0.0.1:2", "local_runtime": {"auto_start": False}})
        self.assertEqual(runtime.endpoint, "http://127.0.0.1:2")

    def test_runtime_starts_ollama_without_privileged_systemctl(self):
        runtime = LocalModelRuntime({"ollama_url": "http://127.0.0.1:1"})
        runtime.binary = "/usr/bin/ollama"
        process = type("Process", (), {"poll": lambda self: None})()
        with patch.object(runtime, "_healthy", side_effect=[False, True]), patch(
            "ada.infrastructure.runtime.ollama.subprocess.Popen", return_value=process
        ) as popen, patch("ada.infrastructure.runtime.ollama.subprocess.run") as systemctl:
            status = runtime.start()

        self.assertTrue(status.available)
        self.assertEqual(status.reason, "started_by_ada")
        popen.assert_called_once()
        systemctl.assert_not_called()

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

    def test_automatic_modes_choose_only_installed_hardware_safe_models(self):
        manager = ModelManager({"local_runtime": {"auto_start": False}})
        names = [
            "llama3.2:3b",
            "qwen2.5:7b",
            "qwen3:8b",
            "deepseek-r1:8b",
            "deepseek-r1:14b",
            "deepseek-r1:32b",
            "qwen2.5-coder:14b",
            "deepseek-coder-v2:16b",
        ]
        installed = [manager._profile_for_model(name) for name in names]
        hardware = {"ram_gb": 14.9, "cpu_cores": 8, "gpu_backend": "cpu"}

        light = manager.automatic_policy("light", installed, hardware)
        hybrid = manager.automatic_policy("hybrid", installed, hardware)
        turbo = manager.automatic_policy("turbo", installed, hardware)

        self.assertEqual(light["chat"]["preferred"], "llama3.2:3b")
        self.assertEqual(light["router"]["preferred"], "llama3.2:3b")
        self.assertEqual(hybrid["chat"]["preferred"], "llama3.2:3b")
        self.assertEqual(hybrid["reasoning"]["preferred"], "deepseek-r1:8b")
        self.assertEqual(hybrid["coding"]["preferred"], "qwen2.5:7b")
        self.assertEqual(turbo["reasoning"]["preferred"], "deepseek-r1:14b")
        self.assertEqual(turbo["coding"]["preferred"], "deepseek-coder-v2:16b")
        self.assertNotIn("deepseek-r1:32b", str(turbo))

    def test_task_role_switches_between_chat_reasoning_and_coding(self):
        self.assertEqual(ModelManager.role_for_task({"prompt": "hola", "complexity": 2}), "chat")
        self.assertEqual(ModelManager.role_for_task({"prompt": "resolvé este problema", "complexity": 8}), "reasoning")
        self.assertEqual(ModelManager.role_for_task({"prompt": "refactorizá este código", "complexity": 4}), "coding")

    def test_mode_runtime_settings_scale_with_available_cpu(self):
        profile = {"cpu_cores": 8, "ram_gb": 14.9}
        self.assertEqual(ModelManager.runtime_settings_for_mode("light", profile)["ollama_num_thread"], 4)
        self.assertEqual(ModelManager.runtime_settings_for_mode("hybrid", profile)["ollama_num_thread"], 6)
        self.assertEqual(ModelManager.runtime_settings_for_mode("turbo", profile)["ollama_num_thread"], 8)
        self.assertGreater(
            ModelManager.runtime_settings_for_mode("hybrid", profile)["model_role_max_tokens"]["coding"],
            ModelManager.runtime_settings_for_mode("hybrid", profile)["model_role_max_tokens"]["chat"],
        )
        for mode in ("light", "hybrid", "turbo"):
            settings = ModelManager.runtime_settings_for_mode(mode, profile)
            self.assertNotIn("model_timeout", settings)
            self.assertNotIn("chat_timeout_seconds", settings)


if __name__ == "__main__":
    unittest.main()
