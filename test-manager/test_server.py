import json
import os
import tempfile
import unittest

import server


class TestManagerPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        server.DB = os.path.join(self.directory.name, "manager.sqlite")

    def tearDown(self):
        self.directory.cleanup()

    def test_seed_contains_smoke_prompts(self):
        connection = server.db()
        categories = connection.execute("SELECT name FROM categories").fetchall()
        prompts = connection.execute("SELECT name FROM prompts ORDER BY id").fetchall()
        self.assertEqual(["Smoke tests"], [item[0] for item in categories])
        self.assertEqual(3, len(prompts))
        connection.close()

    def test_evaluation_flags_missing_tool_and_unsupported_rag(self):
        test = {
            "expected_tools": ["web_search"],
            "expected_memories": [],
            "expected_context": [],
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


if __name__ == "__main__":
    unittest.main()
