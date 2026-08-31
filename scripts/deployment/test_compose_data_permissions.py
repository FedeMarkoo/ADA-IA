"""Contract tests for persistent data ownership in Docker Compose."""

import unittest
from pathlib import Path


COMPOSE = Path(__file__).parents[2] / "compose.yaml"


class ComposeDataPermissionsTest(unittest.TestCase):
    def test_mcp_service_uses_published_image(self):
        content = COMPOSE.read_text()

        self.assertIn(
            "image: ${ADA_MCP_IMAGE:-ghcr.io/fedemarkoo/ada-mcps}:${ADA_MCP_VERSION:-latest}",
            content,
        )
        self.assertNotIn("ada-mcps:\n    build: ./mcp", content)

    def test_data_initializer_does_not_take_autodeployer_paths(self):
        content = COMPOSE.read_text()

        self.assertIn("/ada-data/backups", content)
        self.assertIn("/ada-data/db", content)
        self.assertNotIn("chown -R $${ADA_CONTAINER_UID:-10001}:$${ADA_CONTAINER_GID:-10001} /ada-data /test-manager-data", content)


if __name__ == "__main__":
    unittest.main()
