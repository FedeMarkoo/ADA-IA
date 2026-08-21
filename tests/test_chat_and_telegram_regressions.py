import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ada.application.services.web_chat import WebChatService, _resolve_path_alias
from telegram.bot import TelegramListener


class ChatPathRegressionTests(unittest.TestCase):
    def test_common_path_aliases_resolve(self):
        self.assertEqual(_resolve_path_alias("Escritorio"), "~/Desktop".replace("~", __import__("os").path.expanduser("~")))
        self.assertEqual(_resolve_path_alias("el escritorio"), __import__("os").path.expanduser("~/Desktop"))
        self.assertEqual(_resolve_path_alias("~/Desktop"), __import__("os").path.expanduser("~/Desktop"))

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
        self.assertTrue(hasattr(state, "pending_path_action"))
        self.assertIn("ruta", first["reply"].lower() + "carpeta" + first["reply"].lower())

        second, status = service.handle("Escritorio", state, "es")
        self.assertEqual(status, 200)
        self.assertEqual(second["reply"], "archivos encontrados")
        self.assertFalse(getattr(state, "pending_path_action", None))
        self.assertEqual(calls[0]["payload"]["dir"], __import__("os").path.expanduser("~/Desktop"))


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

    def test_internal_chat_does_not_retry_side_effecting_request(self):
        bot = TelegramListener({"telegram": {"token": "test"}})
        bot._invoke_internal_chat = Mock(return_value="respuesta")
        bot.send_message = Mock()
        bot.handle_update({
            "update_id": 1,
            "message": {"chat": {"id": 10}, "from": {"id": 20}, "text": "hola"},
        })
        bot.handle_update({
            "update_id": 1,
            "message": {"chat": {"id": 10}, "from": {"id": 20}, "text": "hola"},
        })
        self.assertEqual(bot._invoke_internal_chat.call_count, 2)


if __name__ == "__main__":
    unittest.main()
