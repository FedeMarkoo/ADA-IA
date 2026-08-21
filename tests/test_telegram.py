import unittest
from telegram.bot import TelegramListener


class TelegramAdapterTests(unittest.TestCase):
    def test_disabled_without_token(self):
        listener = TelegramListener({"telegram": {"enabled": True, "token": ""}})
        self.assertFalse(listener.enabled)

    def test_allowed_chat_ids_are_normalized(self):
        listener = TelegramListener({"telegram": {"allowed_chat_ids": [123, " 456 "]}})
        self.assertEqual(listener.allowed_chat_ids, {"123", "456"})

    def test_photo_message_builds_internal_prompt(self):
        listener = TelegramListener({"telegram": {"enabled": False}})
        listener._download_photo = lambda photo: "/tmp/photo.jpg"
        listener._invoke_internal_chat = lambda text: text
        sent = []
        listener.send_message = lambda chat_id, text: sent.append((chat_id, text))
        listener.handle_update({"message": {"chat": {"id": 7}, "caption": "analizala", "photo": [{"file_id": "x"}]}})
        self.assertEqual(sent[0][0], "7")
        self.assertIn("/tmp/photo.jpg", sent[0][1])

    def test_logs_chat_id(self):
        listener = TelegramListener({"telegram": {"enabled": False}})
        listener._invoke_internal_chat = lambda text: text
        listener.send_message = lambda chat_id, text: None
        with self.assertLogs("ada.telegram", level="INFO") as logs:
            listener.handle_update({"message": {"chat": {"id": 987654321}, "text": "hola"}})
        self.assertIn("chat_id=987654321", "\n".join(logs.output))

    def test_commands_are_handled_at_the_edge(self):
        listener = TelegramListener({"telegram": {"enabled": False}})
        sent = []
        listener.send_message = lambda chat_id, text: sent.append((chat_id, text))
        listener.handle_update({"message": {"chat": {"id": 9}, "text": "/help"}})
        self.assertIn("/status", sent[0][1])


if __name__ == "__main__":
    unittest.main()
