#!/usr/bin/env python3
"""Contract tests for the Linux autodeployer unit."""

import unittest
from pathlib import Path


SERVICE = Path(__file__).parents[2] / "deploy" / "ada-deployer.service"


class AutodeployerServiceTest(unittest.TestCase):
    def test_service_is_renderable_and_restarts_deployer(self):
        content = SERVICE.read_text()

        for placeholder in (
            "@ADA_USER@",
            "@ADA_GROUP@",
            "@ADA_HOME@",
            "@ADA_DIR@",
            "@ADA_ENV_FILE@",
        ):
            self.assertIn(placeholder, content)

        self.assertIn("After=docker.service network-online.target", content)
        self.assertIn("ExecStartPre=/usr/bin/docker info", content)
        self.assertIn("SupplementaryGroups=docker 10001", content)
        self.assertIn("Restart=always", content)
        self.assertIn("WantedBy=multi-user.target", content)


if __name__ == "__main__":
    unittest.main()
