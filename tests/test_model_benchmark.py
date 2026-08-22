import json
import unittest
from unittest.mock import MagicMock, patch

from ada.models.benchmark import BENCHMARK_PROMPTS, ModelBenchmark


class TestModelBenchmark(unittest.TestCase):
    def setUp(self):
        self.benchmark = ModelBenchmark("http://127.0.0.1:11434")

    def test_get_prompt_catalog(self):
        catalog = self.benchmark.get_prompt_catalog()
        self.assertIn("quick", catalog)
        self.assertIn("reasoning", catalog)
        self.assertIn("json", catalog)
        self.assertIn("planning", catalog)
        self.assertIn("coding", catalog)
        self.assertEqual(catalog["quick"]["title"], "Respuesta Rápida")

    @patch("urllib.request.urlopen")
    def test_run_single_prompt_success(self, mock_urlopen):
        fake_response = {
            "response": "Un agente autónomo es un sistema de software...",
            "eval_count": 45,
            "prompt_eval_count": 12,
            "eval_duration": 1_200_000_000,  # 1.2s -> ~37.5 t/s
            "prompt_eval_duration": 150_000_000,  # 150ms TTFT
        }
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.read.return_value = json.dumps(fake_response).encode("utf-8")
        mock_urlopen.return_value = mock_ctx

        result = self.benchmark.run("llama3:8b", prompt_key="quick")
        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "llama3:8b")
        self.assertEqual(result["eval_count"], 45)
        self.assertEqual(result["prompt_eval_count"], 12)
        self.assertGreater(result["tokens_per_second"], 30.0)
        self.assertEqual(result["ttft_ms"], 150.0)
        self.assertIn("resources", result)
        self.assertIn("cpu_percent", result["resources"])
        self.assertIn("ram_used_gb", result["resources"])

    @patch("urllib.request.urlopen")
    def test_run_custom_prompt(self, mock_urlopen):
        fake_response = {
            "response": "Respuesta al prompt personalizado.",
            "eval_count": 20,
            "eval_duration": 500_000_000,
        }
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.read.return_value = json.dumps(fake_response).encode("utf-8")
        mock_urlopen.return_value = mock_ctx

        result = self.benchmark.run("qwen2.5:7b", custom_prompt="¿Cuál es el mejor formato RAW?")
        self.assertTrue(result["ok"])
        self.assertEqual(result["prompt"], "¿Cuál es el mejor formato RAW?")
        self.assertEqual(result["prompt_title"], "Prompt Personalizado")

    @patch.object(ModelBenchmark, "run")
    def test_run_suite(self, mock_run):
        mock_run.side_effect = [
            {
                "ok": True,
                "prompt_key": "quick",
                "prompt_title": "Respuesta Rápida",
                "tokens_per_second": 40.0,
                "ttft_ms": 120.0,
                "eval_count": 50,
                "total_tokens": 60,
                "total_time_s": 1.2,
                "resources": {"cpu_percent": 35.0, "ram_used_gb": 4.2},
            },
            {
                "ok": True,
                "prompt_key": "reasoning",
                "prompt_title": "Razonamiento Lógico",
                "tokens_per_second": 35.0,
                "ttft_ms": 150.0,
                "eval_count": 80,
                "total_tokens": 100,
                "total_time_s": 2.1,
                "resources": {"cpu_percent": 45.0, "ram_used_gb": 4.3},
            },
        ]

        suite = self.benchmark.run_suite("llama3:8b", prompt_keys=["quick", "reasoning"])
        self.assertTrue(suite["ok"])
        self.assertTrue(suite["suite_run"])
        self.assertEqual(len(suite["results"]), 2)
        self.assertEqual(suite["summary"]["successful_prompts"], 2)
        self.assertEqual(suite["summary"]["failed_prompts"], 0)
        self.assertEqual(suite["summary"]["avg_tokens_per_second"], 37.5)
        self.assertEqual(suite["summary"]["avg_ttft_ms"], 135.0)
        self.assertEqual(suite["summary"]["total_tokens_generated"], 130)


if __name__ == "__main__":
    unittest.main()
