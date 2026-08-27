import unittest
from unittest.mock import patch

from ada.infrastructure.engines.model_manager import ModelManager


class LocalModelExclusivityTests(unittest.TestCase):
    def test_switch_unloads_other_resident_before_loading_target(self):
        manager = ModelManager(
            {
                "engine_provider": "ollama",
                "ollama_url": "http://127.0.0.1:11434",
                "local_model_exclusive_mode": True,
            }
        )
        client = type("Client", (), {})()
        client.running_models = lambda: [{"name": "old-model", "size_vram": 100}]
        calls = []
        client.unload_model = lambda name: calls.append(("unload", name)) or True
        client.load_model = lambda name, keep_alive=None: calls.append(("load", name)) or True
        with patch("ada.infrastructure.engines.model_manager.OllamaClient", return_value=client):
            result = manager.switch_local_model("new-model")
        self.assertTrue(result["ok"])
        self.assertEqual(calls, [("unload", "old-model"), ("load", "new-model")])

    def test_failed_switch_restores_previous_model(self):
        manager = ModelManager(
            {
                "engine_provider": "ollama",
                "ollama_url": "http://127.0.0.1:11434",
                "local_model_exclusive_mode": True,
            }
        )
        manager._local_resident_model = "old-model"
        client = type("Client", (), {})()
        client.running_models = lambda: [{"name": "old-model", "size_vram": 100}]
        calls = []
        client.unload_model = lambda name: calls.append(("unload", name)) or True
        client.load_model = lambda name, keep_alive=None: calls.append(("load", name)) or name == "old-model"
        with patch("ada.infrastructure.engines.model_manager.OllamaClient", return_value=client):
            result = manager.switch_local_model("new-model")
        self.assertFalse(result["ok"])
        self.assertEqual(manager._local_resident_model, "old-model")
        self.assertEqual(calls, [("unload", "old-model"), ("load", "new-model"), ("load", "old-model")])

    def test_active_request_blocks_manual_unload(self):
        manager = ModelManager({"engine_provider": "ollama", "local_model_exclusive_mode": True})
        manager._local_model_active = 1
        with patch("ada.infrastructure.engines.model_manager.OllamaClient"):
            result = manager.unload_local_model("model")
        self.assertFalse(result["ok"])
        self.assertIn("inferencia activa", result["error"])


if __name__ == "__main__":
    unittest.main()
