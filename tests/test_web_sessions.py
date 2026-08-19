import unittest

try:
    from ada.interfaces.web.server import app
except ImportError:
    app = None


@unittest.skipIf(app is None, "Flask no está instalado en este entorno")
class WebSessionTests(unittest.TestCase):
    def test_conversations_and_pending_state_are_isolated_by_cookie(self):
        first = app.test_client()
        second = app.test_client()
        first.get("/").close()
        second.get("/").close()
        csrf = first.get_cookie("ada_csrf").value
        response = first.post(
            "/api/chat",
            json={"message": "hola", "lang": "es"},
            headers={"X-ADA-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(first.get("/api/conversation").get_json()["messages"]), 2)
        self.assertEqual(len(second.get("/api/conversation").get_json()["messages"]), 0)


if __name__ == "__main__":
    unittest.main()
