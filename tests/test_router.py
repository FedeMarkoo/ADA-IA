import unittest
from pathlib import Path

from src.ada.application.router import IntentRouter


class FakeModelManager:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def choose(self, task):
        return "ollama" if self.response is not None else None

    def call(self, provider, prompt, **kwargs):
        self.calls.append((provider, prompt, kwargs))
        return self.response


class IntentRouterTests(unittest.TestCase):
    def test_fallback_routes_semantically_without_model(self):
        router = IntentRouter(FakeModelManager())
        result = router.route("necesito revisar el enfoque y la exposición de esta imagen")
        self.assertEqual(result["action"], "analyze_photo")

    def test_model_plan_is_validated(self):
        manager = FakeModelManager('{"action":"select_photo_batch","confidence":0.92,"steps":[{"action":"select_photo_batch"}]}')
        result = IntentRouter(manager).route("quiero que selecciones el lote y prepares los xmp")
        self.assertEqual(result["action"], "select_photo_batch")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(manager.calls[0][2]["temperature"], 0)

    def test_invalid_model_action_uses_fallback(self):
        result = IntentRouter(FakeModelManager('{"action":"delete_everything"}')).route("quiero ordenar los archivos")
        self.assertEqual(result["action"], "organize")

    def test_photo_path_can_be_followed_by_more_text(self):
        from src.ada.application.agent import Agent
        agent = Agent({"engine_provider": "unknown", "db_path": ":memory:"})
        result = agent.parse_prompt(
            "Analizá /Users/home/Desktop/Sofia_Batch_200/OK__DSC7939.ARW y decime si está bien"
        )
        self.assertEqual(result["action"], "analyze_photo")
        self.assertEqual(Path(result["path"]).suffix.lower(), ".arw")


if __name__ == "__main__":
    unittest.main()
