#!/usr/bin/env python3
"""Unit tests for the host resource exporter classification rules."""

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("host-resource-exporter.py")
SPEC = importlib.util.spec_from_file_location("host_resource_exporter", MODULE_PATH)
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


class HostResourceExporterTest(unittest.TestCase):
    def test_classifies_application_processes(self):
        self.assertEqual(EXPORTER.classify("java", "java -jar /app/ada.jar"), "ada")
        self.assertEqual(EXPORTER.classify("python", "python -m litellm"), "litellm")
        self.assertEqual(EXPORTER.classify("grafana", "grafana server"), "grafana")
        self.assertEqual(EXPORTER.classify("prometheus", "prometheus --config.file=x"), "prometheus")

    def test_ignores_unrelated_processes(self):
        self.assertIsNone(EXPORTER.classify("java", "java -jar unrelated.jar"))

    def test_system_memory_is_non_negative(self):
        total, available = EXPORTER.system_memory()
        self.assertGreater(total, 0)
        self.assertGreaterEqual(available, 0)
        self.assertLessEqual(available, total)


if __name__ == "__main__":
    unittest.main()
