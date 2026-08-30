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
    def test_data_dir_matches_compose_relative_path(self):
        args = type(
            "Args",
            (),
            {
                "compose": Path("/opt/ada/compose.yaml"),
                "env_file": Path("/opt/ada/../ada-data/.env"),
            },
        )()

        data_dir = DEPLOYER.resolve_data_dir(args, {"ADA_DATA_DIR": "../ada-data"})

        self.assertEqual(data_dir, Path("/opt/ada-data").resolve())

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

    def test_image_id_inspects_configured_mcp_image_tag(self):
        result = subprocess.CompletedProcess([], 0, "sha256:mcp\n", "")
        with patch.object(DEPLOYER.subprocess, "run", return_value=result) as run:
            image = DEPLOYER.image_id(
                None,
                {"ADA_MCP_IMAGE": "example/ada-mcps", "ADA_MCP_VERSION": "v2"},
                "ada-mcps",
            )

        self.assertEqual(image, "sha256:mcp")
        self.assertEqual(run.call_args.args[0][-1], "example/ada-mcps:v2")

    @patch.object(DEPLOYER, "mcp_healthcheck", return_value=True)
    @patch.object(DEPLOYER, "healthcheck", return_value=True)
    @patch.object(DEPLOYER, "backup_database", return_value=None)
    @patch.object(DEPLOYER, "running_image_id", side_effect=["old-ada", "old-mcp"])
    @patch.object(DEPLOYER, "image_id", side_effect=["old-ada", "old-mcp", "new-ada", "new-mcp"])
    @patch.object(DEPLOYER, "compose")
    def test_deploy_pulls_and_starts_ada_and_mcp_images(
        self, compose, image_id, running_image_id, backup_database, healthcheck, mcp_healthcheck
    ):
        args = type(
            "Args",
            (),
            {
                "env_file": Path("/tmp/ada-deployer-test.env"),
                "compose": Path("/tmp/compose.yaml"),
                "health_url": "http://ada/health",
                "health_timeout": 1,
            },
        )()
        with patch.object(DEPLOYER.os, "environ", {"ADA_DATA_DIR": "/tmp"}):
            self.assertEqual(DEPLOYER.deploy(args), 0)

        self.assertTrue(
            any(call.args[2:] == ("pull", "ada", "ada-mcps") for call in compose.call_args_list)
        )
        self.assertTrue(any(call.args[2:] == ("up", "-d") for call in compose.call_args_list))


if __name__ == "__main__":
    unittest.main()
