import unittest

from ada.application.services.responses import text_from_result
from ada.application.services.web_chat import WebChatService


class FilesystemChatRegressionTests(unittest.TestCase):
    def test_large_file_listing_is_summarized(self):
        result = {
            "ok": True,
            "action": "list_files",
            "dir": "/Users/home/Desktop",
            "count": 891,
            "files": [f"/Users/home/Desktop/photo_{i}.ARW" for i in range(891)],
        }
        reply = text_from_result(result)
        self.assertIn("Encontré 891 archivos", reply)
        self.assertIn("Primeros 10:", reply)
        self.assertIn("Hay 881 más", reply)
        self.assertLess(len(reply), 2500)

    def test_folder_listing_is_summarized(self):
        result = {
            "ok": True,
            "action": "list_dirs",
            "dir": "/Users/home/Desktop",
            "count": 42,
            "dirs": [f"/Users/home/Desktop/folder_{i}" for i in range(42)],
        }
        reply = text_from_result(result)
        self.assertIn("Encontré 42 carpetas", reply)
        self.assertIn("Primeros 10:", reply)
        self.assertIn("Hay 32 más", reply)

    def test_folder_question_forces_list_dirs_even_if_router_says_files(self):
        class FakeAgent:
            lang = "es"

            def parse_prompt(self, text):
                return {"action": "list_files", "complexity": 2}

        service = WebChatService(FakeAgent(), {})
        action, payload = service._task(
            {"action": "list_files", "complexity": 2},
            "Que carpetas hay en el escritorio?",
        )
        self.assertEqual(action, "filesystem")
        self.assertEqual(payload["action"], "list_dirs")
        self.assertEqual(payload["dir"], __import__("os").path.expanduser("~/Desktop"))


if __name__ == "__main__":
    unittest.main()
