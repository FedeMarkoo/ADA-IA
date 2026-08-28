#!/usr/bin/env python3
"""Unit tests for local deploy image resolution."""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("local-deployer.py")
SPEC = importlib.util.spec_from_file_location("local_deployer", MODULE_PATH)
DEPLOYER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOYER)


class LocalDeployerTest(unittest.TestCase):
    def test_image_id_inspects_configured_image_tag(self):
        result = subprocess.CompletedProcess([], 0, "sha256:abc\n", "")
        with patch.object(DEPLOYER.subprocess, "run", return_value=result) as run:
            image = DEPLOYER.image_id(
                None,
                {"ADA_IMAGE": "example/ada", "ADA_VERSION": "v1"},
            )

        self.assertEqual(image, "sha256:abc")
        self.assertEqual(
            run.call_args.args[0],
            [
                "docker",
                "image",
                "inspect",
                "--platform",
                "linux/amd64",
                "--format",
                "{{.Id}}",
                "example/ada:v1",
            ],
        )

    def test_image_id_returns_empty_when_image_is_not_local(self):
        result = subprocess.CompletedProcess([], 1, "", "not found")
        with patch.object(DEPLOYER.subprocess, "run", return_value=result):
            image = DEPLOYER.image_id(None, {})

        self.assertEqual(image, "")


if __name__ == "__main__":
    unittest.main()
