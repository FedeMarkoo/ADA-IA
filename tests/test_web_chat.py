import unittest
from unittest.mock import MagicMock

from ada.application.services.web_chat import WebChatService


class DummyState:
    def __init__(self):
        self.conversation = []
        self.pending_action = None
        self.pending_path_action = None
        self.current_path = None


class TestWebChatService(unittest.TestCase):
    def setUp(self):
        self.mock_agent = MagicMock()
        self.config = {"base_dir": "/tmp"}
        self.service = WebChatService(self.mock_agent, self.config)

    def test_version_command(self):
        state = DummyState()
        response, code = self.service.handle("/version", state, lang="es")
        self.assertEqual(code, 200)
        self.assertTrue(response["reply"].startswith("ADA versión"))

    def test_greeting_fast_reply(self):
        state = DummyState()
        response, code = self.service.handle("hola", state, lang="es")
        self.assertEqual(code, 200)
        self.assertEqual(response["model"], "ADA · respuesta rápida")

    def test_empty_message_rejected(self):
        state = DummyState()
        response, code = self.service.handle("   ", state, lang="es")
        self.assertEqual(code, 400)
        self.assertEqual(response["error"], "empty_message")

    def test_cancel_pending_action(self):
        state = DummyState()
        state.pending_action = {"type": "run_script", "payload": {"command": "ls"}}
        response, code = self.service.handle("cancelar", state, lang="es")
        self.assertEqual(code, 200)
        self.assertIsNone(state.pending_action)
        self.assertEqual(response["reply"], "Operación cancelada.")


if __name__ == "__main__":
    unittest.main()
