import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

import server


class TestManagerPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        server.DB = os.path.join(self.directory.name, "manager.sqlite")

    def tearDown(self):
        self.directory.cleanup()

    def test_initialization_creates_empty_test_manager_schema(self):
        connection = server.db()
        categories = connection.execute("SELECT name FROM categories ORDER BY name").fetchall()
        prompts = connection.execute("SELECT name FROM prompts ORDER BY id").fetchall()
        self.assertEqual([], [item[0] for item in categories])
        self.assertEqual([], [item[0] for item in prompts])
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        self.assertEqual(
            ["categories", "executions", "prompts"], [item[0] for item in tables]
        )
        connection.close()

    def test_database_initialization_is_safe_for_concurrent_requests(self):
        def open_and_close(_):
            """Read seeded data before closing a concurrently opened connection."""
            connection = server.db()
            category_count = connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            self.assertEqual(0, category_count)
            connection.close()

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(open_and_close, range(16)))

    def test_evaluation_flags_missing_tool_and_unsupported_rag(self):
        test = {
            "expected_tools": ["web_search"],
            "expected_memories": [],
            "expected_context": [],
            "expected_terms": ["respuesta"],
            "expected_rag": True,
        }
        result = {
            "content": "respuesta",
            "contextSelection": {"memories": [], "mcps": [], "tools": []},
            "executedTools": [],
            "tokenUsage": [{"component": "prompt", "tokens": 10}],
        }
        original = server.run_ada
        server.run_ada = lambda _: {"content": json.dumps({"score": 4, "verdict": "fail", "findings": []})}
        try:
            evaluation = server.evaluate(test, result)
        finally:
            server.run_ada = original
        self.assertFalse(evaluation["checks"]["expected_tools_executed"])
        self.assertFalse(evaluation["checks"]["rag_available"])
        self.assertEqual(result["tokenUsage"], evaluation["token_usage"])

    def test_evaluation_rejects_answer_missing_expected_terms(self):
        test = {"expected_tools": [], "expected_memories": [], "expected_context": [], "expected_terms": ["dominio", "aplicación"], "expected_rag": False}
        result = {"content": "Sólo habla de infraestructura.", "contextSelection": {}, "executedTools": [], "tokenUsage": []}
        original = server.run_ada
        server.run_ada = lambda _: {"content": json.dumps({"score": 8, "verdict": "pass", "findings": []})}
        try:
            evaluation = server.evaluate(test, result)
        finally:
            server.run_ada = original
        self.assertFalse(evaluation["checks"]["expected_terms_present"])

    def test_run_ada_polls_until_completed_state(self):
        original_request_json = server.request_json
        original_timeout = server.ADA_TIMEOUT_SECONDS
        original_poll = server.ADA_POLL_SECONDS
        calls = []
        server.ADA_TIMEOUT_SECONDS = 1
        server.ADA_POLL_SECONDS = 0

        def request_json(url, payload=None, timeout=180):
            calls.append((url, payload, timeout))
            if url.endswith("/chat"):
                return {"messageId": "message-1"}
            if url.endswith("/status"):
                return {"state": "completed"}
            return {"messageId": "message-1", "content": "respuesta correcta"}

        server.request_json = request_json
        try:
            result = server.run_ada("hola", "conversation-test")
        finally:
            server.request_json = original_request_json
            server.ADA_TIMEOUT_SECONDS = original_timeout
            server.ADA_POLL_SECONDS = original_poll

        self.assertEqual("respuesta correcta", result["content"])
        self.assertEqual("conversation-test", calls[0][1]["conversationId"])

    def test_run_ada_uses_isolated_conversation_when_not_provided(self):
        original_request_json = server.request_json
        calls = []

        def request_json(url, payload=None, timeout=180):
            calls.append(payload)
            if url.endswith("/chat"):
                return {"messageId": "message-2"}
            if url.endswith("/status"):
                return {"state": "completed"}
            return {"content": "ok"}

        server.request_json = request_json
        try:
            server.run_ada("hola")
        finally:
            server.request_json = original_request_json

        self.assertTrue(calls[0]["conversationId"].startswith("test-manager-"))


if __name__ == "__main__":
    unittest.main()
