import unittest
from ada.application.tool_registry import ToolRegistry
from pathlib import Path
import tempfile

from ada.application.router import IntentRouter
from ada.infrastructure.persistence.sqlite import Memory


class FakeModelManager:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def choose(self, task):
        return "ollama" if self.response is not None else None

    def call(self, provider, prompt, **kwargs):
        self.calls.append((provider, prompt, kwargs))
        return self.response

    def select_model(self, task, role="chat"):
        return "router-model"


class FakeMCPManager:
    def list_tools(self):
        return [
            {"name": "google_calendar.list_calendars", "enabled": True, "requires_confirmation": False},
            {"name": "google_calendar.list_events", "enabled": True, "requires_confirmation": False},
        ]


class IntentRouterTests(unittest.TestCase):
    def test_tool_registry_rejects_missing_required_parameters(self):
        tool = {"parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}
        self.assertFalse(ToolRegistry.validate_parameters(tool, {}))
        self.assertTrue(ToolRegistry.validate_parameters(tool, {"path": "/tmp"}))

    def setUp(self):
        self.memory = Memory(":memory:")

    def router(self, manager):
        return IntentRouter(manager, memory=self.memory)

    def test_requires_explicit_memory(self):
        with self.assertRaises(ValueError):
            IntentRouter(FakeModelManager())

    def test_fallback_routes_semantically_without_model(self):
        router = self.router(FakeModelManager())
        result = router.route("necesito revisar el enfoque y la exposición de esta imagen")
        self.assertEqual(result["action"], "analyze_photo")

    def test_plain_conversation_does_not_start_router_model(self):
        manager = FakeModelManager('{"action":"ask"}')
        result = self.router(manager).route("explicame por qué el cielo se ve azul")
        self.assertEqual(result["action"], "ask")
        self.assertEqual(manager.calls, [])

    def test_capability_discussion_is_not_executed_as_a_file_command(self):
        manager = FakeModelManager('{"action":"organize"}')
        result = self.router(manager).route(
            "Analizá las ventajas y riesgos de usar un agente local para organizar archivos, "
            "compará tres enfoques y dame una recomendación."
        )
        self.assertEqual(result["action"], "ask")
        self.assertEqual(manager.calls, [])

    def test_model_plan_is_validated(self):
        manager = FakeModelManager(
            '{"action":"select_photo_batch","confidence":0.92,"steps":[{"action":"select_photo_batch"}]}'
        )
        result = self.router(manager).route("quiero que selecciones el lote y prepares los xmp")
        self.assertEqual(result["action"], "select_photo_batch")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(manager.calls[0][2]["temperature"], 0)

    def test_model_routes_food_semantically(self):
        manager = FakeModelManager(
            '{"action":"food","domain":"recipes","food_action":"advise","advisor":true,"confidence":0.97}'
        )
        result = self.router(manager).route("¿Qué puedo comer mañana según mis gustos?")
        self.assertEqual(result["action"], "food")
        self.assertEqual(result["food_action"], "advise")

    def test_normalizes_model_food_compound_action(self):
        manager = FakeModelManager('{"action":"food/advise","needs_clarification":true}')
        result = self.router(manager).route("¿Qué puedo cocinar?")
        self.assertEqual(result["action"], "food")
        self.assertEqual(result["food_action"], "advise")

    def test_invalid_model_action_uses_fallback(self):
        result = self.router(FakeModelManager('{"action":"delete_everything"}')).route("quiero ordenar los archivos")
        self.assertEqual(result["action"], "organize")

    def test_model_selects_a_valid_readonly_mcp_tool(self):
        manager = FakeModelManager('{"action":"mcp_call","tool":"google_calendar.list_calendars","parameters":{}}')
        router = IntentRouter(manager, memory=self.memory, mcp_manager=FakeMCPManager())
        result = router.route("Listá mis calendarios de Google Calendar")
        self.assertEqual(result["action"], "mcp_call")
        self.assertEqual(result["tool"], "google_calendar.list_calendars")

    def test_external_router_timeout_does_not_fall_through_to_chat_model(self):
        class TimeoutModel(FakeModelManager):
            def __init__(self):
                super().__init__(response="unused")

            def call(self, provider, prompt, **kwargs):
                raise TimeoutError("router timeout")

        result = IntentRouter(TimeoutModel(), memory=self.memory, mcp_manager=FakeMCPManager()).route(
            "¿Cuál es mi próximo evento de Google Calendar?"
        )
        self.assertEqual(result["action"], "ask")
        self.assertEqual(result["routing_error"], "mcp_router_failed")

    def test_truncated_mcp_json_recovers_only_explicit_tool(self):
        manager = FakeModelManager('{"action":"mcp_call","tool":"google_calendar.list_events"')
        router = IntentRouter(manager, memory=self.memory, mcp_manager=FakeMCPManager())
        result = router.route("¿Qué eventos próximos tengo en Google Calendar?")
        self.assertEqual(result["action"], "mcp_call")
        self.assertEqual(result["tool"], "google_calendar.list_events")

    def test_photo_path_can_be_followed_by_more_text(self):
        from ada.application.agent import Agent

        with tempfile.TemporaryDirectory() as directory:
            agent = Agent({"engine_provider": "unknown", "db_path": str(Path(directory) / "test.db")})
            result = agent.parse_prompt(
                "Analizá /Users/home/Desktop/Sofia_Batch_200/OK__DSC7939.ARW y decime si está bien"
            )
        self.assertEqual(result["action"], "analyze_photo")
        self.assertEqual(Path(result["path"]).suffix.lower(), ".arw")

    def test_agent_rules_keep_capability_discussion_in_chat(self):
        from ada.application.agent import Agent

        with tempfile.TemporaryDirectory() as directory:
            agent = Agent({"engine_provider": "unknown", "db_path": str(Path(directory) / "test.db")})
            result = agent.parse_prompt(
                "Analizá con calma las ventajas y riesgos de organizar archivos personales y compará enfoques."
            )
            self.assertEqual(result["action"], "ask")

    def test_calendar_queries_are_not_confused_with_filesystem_tasks(self):
        from ada.application.agent import Agent

        with tempfile.TemporaryDirectory() as directory:
            agent = Agent({"engine_provider": "unknown", "db_path": str(Path(directory) / "test.db")})
            result = agent.parse_prompt("Cual es mi próximo evento en calendar?")
            # Consultas de calendario no deben mutar archivos ni exigir rutas locales de disco
            self.assertIn(
                result.get("action"),
                {None, "ask", "suggest", "google_calendar.list_events", "google_calendar.search_events"},
            )


if __name__ == "__main__":
    unittest.main()
