import unittest

from ada.config import validate_config


class ConfigTests(unittest.TestCase):
    def test_validation_rejects_unknown_web_framework(self):
        with self.assertRaises(ValueError):
            validate_config({"web_framework": "unknown"})

    def test_validation_accepts_model_catalog_shapes(self):
        config = validate_config({"model_catalog": {"small": {"min_ram_gb": 2}}})
        self.assertEqual(config["model_catalog"]["small"]["min_ram_gb"], 2)

    def test_validation_rejects_non_boolean_memory_encryption(self):
        with self.assertRaises(ValueError):
            validate_config({"memory_encryption": "yes"})

    def test_validation_rejects_invalid_runtime_types(self):
        with self.assertRaises(ValueError):
            validate_config({"adaptive_models": "yes"})
        with self.assertRaises(ValueError):
            validate_config({"photo_executor": "fork"})
        with self.assertRaises(ValueError):
            validate_config({"cpu_limit_percent": 0})
        with self.assertRaises(ValueError):
            validate_config({"chat_workers": 0})

    def test_validation_accepts_patient_agent_timeouts(self):
        config = validate_config(
            {
                "timeout_profile": "patient",
                "router_timeout": 30,
                "model_timeout": 300,
                "chat_timeout_seconds": 900,
                "food_advisor_timeout": 180,
            }
        )
        self.assertEqual(config["chat_timeout_seconds"], 900)

    def test_validation_rejects_incoherent_or_excessive_timeouts(self):
        with self.assertRaises(ValueError):
            validate_config({"model_timeout": 600, "chat_timeout_seconds": 300})
        with self.assertRaises(ValueError):
            validate_config({"chat_timeout_seconds": 90000})
        with self.assertRaises(ValueError):
            validate_config({"timeout_profile": "forever"})


if __name__ == "__main__":
    unittest.main()
