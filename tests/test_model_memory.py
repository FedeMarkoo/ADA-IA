import unittest

from ada.application.services.model_memory import ModelMemoryEstimator


class ModelMemoryEstimatorTests(unittest.TestCase):
    def test_context_increases_kv_and_total_memory(self):
        estimator = ModelMemoryEstimator()
        metadata = {"size": 3 * 1024**3, "details": {"parameter_size": "3B", "quantization_level": "Q4_K_M"}}
        small = estimator.estimate(
            "llama3.2:3b", 4096, metadata=metadata, hardware={"ram_available_gb": 16, "ram_gb": 16}
        )
        large = estimator.estimate(
            "llama3.2:3b", 16384, metadata=metadata, hardware={"ram_available_gb": 16, "ram_gb": 16}
        )
        self.assertGreater(large["estimate"]["kv_cache_bytes"], small["estimate"]["kv_cache_bytes"])
        self.assertGreater(large["estimate"]["total_bytes"], small["estimate"]["total_bytes"])

    def test_observed_ollama_memory_has_high_confidence(self):
        result = ModelMemoryEstimator().estimate(
            "model",
            8192,
            metadata={"size": 2 * 1024**3},
            running=[{"name": "model", "size_vram": 4 * 1024**3}],
            hardware={"ram_available_gb": 16, "ram_gb": 16},
        )
        self.assertEqual(result["estimate"]["source"], "observed_ollama")
        self.assertEqual(result["estimate"]["confidence"], "high")

    def test_invalid_context_is_clamped(self):
        result = ModelMemoryEstimator().estimate("model", 1, metadata={})
        self.assertEqual(result["context"]["num_ctx"], 512)


if __name__ == "__main__":
    unittest.main()
