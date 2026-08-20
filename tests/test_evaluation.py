import unittest

from ada.application.evaluation import EvaluationCase, evaluate


class EvaluationHarnessTests(unittest.TestCase):
    def test_evaluation_reports_router_accuracy(self):
        class FakeAgent:
            @staticmethod
            def parse_prompt(prompt):
                return {"action": "food" if "receta" in prompt else "ask"}

        result = evaluate(
            FakeAgent(),
            [
                EvaluationCase("recipe", "dame una receta", "food"),
                EvaluationCase("question", "hola", "ask"),
            ],
        )
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["passed"], 2)


if __name__ == "__main__":
    unittest.main()
