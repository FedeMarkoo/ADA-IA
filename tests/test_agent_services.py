import unittest

from ada.application.services.complexity import ComplexityEstimator
from ada.application.services.prompts import PromptBuilder
from ada.application.services.responses import text_from_result
from ada.infrastructure.persistence.sqlite import Memory


class AgentServiceTests(unittest.TestCase):
    def test_complexity_estimator_is_independent(self):
        self.assertEqual(ComplexityEstimator.estimate("mostrame el reporte"), 2)
        self.assertEqual(ComplexityEstimator.estimate("analizá este caso complejo"), 8)

    def test_prompt_builder_uses_memory_context(self):
        memory = Memory(":memory:")
        memory.add_knowledge("regla", "regla confiable")
        prompt = PromptBuilder(memory).task({"prompt": "regla"}, "es")
        self.assertIn("regla confiable", prompt)
        self.assertIn("Responde en español", prompt)

    def test_response_normalization_only_reads_structured_fields(self):
        self.assertEqual(text_from_result({"reply": "respuesta"}), "respuesta")
        self.assertEqual(text_from_result({"result": {"ok": True}}), "{'ok': True}")


if __name__ == "__main__":
    unittest.main()
