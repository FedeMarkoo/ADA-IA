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

    def test_openai_client_is_reused_for_same_provider_endpoint(self):
        class FakeCompletions:
            def create(self, **_kwargs):
                return type(
                    "Response",
                    (),
                    {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]},
                )()

        fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})()
        with patch("ada.infrastructure.engines.model_manager.OpenAI", return_value=fake_client) as factory:
            self.assertEqual(self.manager._call_openai("one", api_key="key"), "ok")
            self.assertEqual(self.manager._call_openai("two", api_key="key"), "ok")
        factory.assert_called_once_with(api_key="key", base_url=None)

    def test_route_hints_resolve_to_allowlisted_role_and_fallbacks(self):
        manager = ModelManager(
            {
                "model_policy": {"reasoning": {"preferred": "reasoner", "fallbacks": ["small"]}},
                "models": {"reasoning": "reasoner"},
                "engine_provider": "unknown",
            }
        )
        selection = manager.select_model_for_route({"task_type": "reasoning", "complexity": 8})
        self.assertEqual(selection["role"], "reasoning")
        self.assertEqual(selection["model"], "reasoner")
        self.assertIn("small", selection["fallbacks"])

    def test_litellm_ollama_backend_uses_prefixed_local_model(self):
        class Message:
            content = "respuesta local"

        fake_response = type("Response", (), {"choices": [type("Choice", (), {"message": Message()})()]})()
        manager = ModelManager({"ollama_backend": "litellm", "ollama_url": "http://127.0.0.1:11434"})
        with patch("ada.infrastructure.engines.model_manager.litellm_completion", return_value=fake_response) as call:
            result = manager._call_ollama("hola", ollama_model="llama3.2:3b")
        self.assertEqual(result, "respuesta local")
        self.assertEqual(call.call_args.kwargs["model"], "ollama/llama3.2:3b")
        self.assertEqual(call.call_args.kwargs["api_base"], manager.ollama_url)

    def test_automatic_policy_is_cached_until_reload(self):
        manager = ModelManager({"model_selection_mode": "light", "local_runtime": {"auto_start": False}})
        with patch.object(manager, "automatic_policy", return_value={"chat": {"preferred": "small"}}) as build:
            self.assertEqual(manager.effective_policy(), manager.effective_policy())
        build.assert_called_once_with("light")


if __name__ == "__main__":
    unittest.main()
