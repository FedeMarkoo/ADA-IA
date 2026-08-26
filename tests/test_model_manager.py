import unittest
from unittest.mock import patch

from ada.infrastructure.engines.model_manager import ModelManager


class TestModelManager(unittest.TestCase):
    def setUp(self):
        self.config = {
            "engine_provider": "ollama",
            "privacy_default": "normal",
            "local_max_complexity": 4,
            "engine_priority": ["openai", "anthropic", "ollama"],
            "ollama_url": "http://127.0.0.1:11434",
        }
        self.manager = ModelManager(self.config)

    def test_choose_privacy_high(self):
        # Even with OpenAI available, privacy=high should route to local/ollama
        with patch.object(self.manager, "available", return_value={"ollama": True, "local": True, "openai": True}):
            chosen = self.manager.choose({"complexity": 8, "privacy": "high"})
            self.assertEqual(chosen, "ollama")

    def test_choose_low_complexity_local(self):
        # Complexity 3 <= 4 -> should route to local provider
        with patch.object(self.manager, "available", return_value={"ollama": True, "local": True, "openai": True}):
            chosen = self.manager.choose({"complexity": 3, "privacy": "normal"})
            self.assertEqual(chosen, "ollama")

    def test_choose_high_complexity_priority(self):
        # Complexity 8 > 4 and openai available -> should select openai
        self.manager.provider = "custom_unavailable"
        with patch.object(self.manager, "available", return_value={"ollama": False, "openai": True}):
            chosen = self.manager.choose({"complexity": 8, "privacy": "normal"})
            self.assertEqual(chosen, "openai")

    def test_apply_config_and_reload(self):
        new_config = {
            "engine_provider": "gemini",
            "ollama_url": "http://localhost:11434",
            "privacy_default": "high",
        }
        self.manager.reload(new_config)
        self.assertEqual(self.manager.provider, "gemini")
        self.assertEqual(self.manager.config["privacy_default"], "high")

    def test_automatic_policy_is_cached_until_reload(self):
        manager = ModelManager({"model_selection_mode": "light", "local_runtime": {"auto_start": False}})
        with patch.object(manager, "automatic_policy", return_value={"chat": {"preferred": "small"}}) as build:
            self.assertEqual(manager.effective_policy(), manager.effective_policy())
        build.assert_called_once_with("light")


if __name__ == "__main__":
    unittest.main()
