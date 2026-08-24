import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ada.application.services.web_chat import WebChatService, _resolve_path_alias
from telegram.bot import TelegramListener


class ChatPathRegressionTests(unittest.TestCase):
    def test_conceptual_photo_comparison_is_not_filesystem_intent(self):
        text = (
            "Compará tres enfoques para organizar fotos personales, explicá riesgos "
            "y terminá con una recomendación concreta."
        )
        self.assertIsNone(WebChatService._filesystem_intent(text))

    def test_general_permission_explanation_is_not_directory_listing(self):
        text = "Necesito una explicación general de cómo funcionan los permisos de una carpeta, sin acceder ni cambiar ningún archivo."
        self.assertIsNone(WebChatService._filesystem_intent(text))

    def test_conceptual_photo_comparison_does_not_resolve_pictures_alias(self):
        calls = []

        class FakeAgent:
            lang = "es"

            def parse_prompt(self, text, history=None):
                return {"action": "ask", "complexity": 4}

            def decide_and_run(self, task):
                calls.append(task)
                return {"result": "Comparación conceptual con recomendación.", "model": "test"}

        state = SimpleNamespace(conversation=[], pending_action=None, pending_path_action=None, current_path=None)
        response, status = WebChatService(FakeAgent(), {}).handle(
            "Compará tres enfoques para organizar fotos personales, explicá riesgos y terminá con una recomendación concreta.",
            state,
            "es",
        )
        self.assertEqual(status, 200)
        self.assertIn("recomendación", response["reply"])
        self.assertEqual(len(calls), 1)

    def test_common_path_aliases_resolve(self):
        desktop = os.path.expanduser("~/Desktop")
        self.assertEqual(_resolve_path_alias("Escritorio"), desktop)
        self.assertEqual(_resolve_path_alias("el escritorio"), desktop)
        self.assertEqual(_resolve_path_alias("~/Desktop"), desktop)

    def test_pending_path_is_resumed_on_follow_up_message(self):
        calls = []

        class FakeAgent:
            lang = "es"

            def parse_prompt(self, text):
                return {"action": "list_files", "complexity": 2}

            def decide_and_run(self, task):
                calls.append(task)
                return {"result": "archivos encontrados", "model": "test"}

        state = SimpleNamespace(conversation=[], pending_action=None)
        service = WebChatService(FakeAgent(), {})

        first, status = service.handle("Listame los archivos", state, "es")
        self.assertEqual(status, 200)
        self.assertTrue(getattr(state, "pending_path_action", None))
        self.assertIn("ruta", first["reply"].lower())

        second, status = service.handle("Escritorio", state, "es")
        self.assertEqual(status, 200)
        self.assertEqual(second["reply"], "archivos encontrados")
        self.assertFalse(getattr(state, "pending_path_action", None))
        self.assertEqual(calls[0]["payload"]["dir"], os.path.expanduser("~/Desktop"))

    def test_generic_followup_receives_only_the_current_session_context(self):
        captured = {}

        class FakeAgent:
            lang = "es"

            def parse_prompt(self, text, history=None):
                captured["router_history"] = history
                return {"action": "ask", "complexity": 3}

            def decide_and_run(self, task):
                captured["task"] = task
                return {"result": "respuesta contextual", "model": "test"}

        state = SimpleNamespace(
            conversation=[
                {"role": "user", "text": "Contame sobre la carpeta Viajes"},
                {"role": "assistant", "text": "La carpeta tiene fotos de Bariloche."},
            ],
            pending_action=None,
            pending_path_action=None,
            current_path=None,
        )
        service = WebChatService(FakeAgent(), {})

        response, status = service.handle("resumime eso", state, "es")

        self.assertEqual(status, 200)
        self.assertEqual(response["reply"], "respuesta contextual")
        self.assertIn("Bariloche", captured["router_history"])
        self.assertIn("Bariloche", captured["task"]["conversation_context"])


class TelegramRegressionTests(unittest.TestCase):
    def test_processed_update_ids_are_bounded_and_deduplicated(self):
        bot = TelegramListener({"telegram": {"token": "test"}})
        bot._remember_update(123)
        bot._remember_update(123)
        self.assertEqual(len(bot._processed_update_ids), 1)

        for update_id in range(2048, 4096):
            bot._remember_update(update_id)
        self.assertNotIn(123, bot._processed_update_ids)
        self.assertIn(4095, bot._processed_update_ids)

    def test_duplicate_update_is_not_processed_twice(self):
        bot = TelegramListener({"telegram": {"token": "test"}})
        bot._invoke_internal_chat = Mock(return_value="respuesta")
        bot.send_message = Mock()
        update = {
            "update_id": 1,
            "message": {"chat": {"id": 10}, "from": {"id": 20}, "text": "hola"},
        }
        bot.handle_update(update)
        bot.handle_update(update)
        self.assertEqual(bot._invoke_internal_chat.call_count, 1)
        self.assertEqual(bot.send_message.call_count, 1)


if __name__ == "__main__":
    unittest.main()
