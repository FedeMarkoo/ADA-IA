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


if __name__ == "__main__":
    unittest.main()
