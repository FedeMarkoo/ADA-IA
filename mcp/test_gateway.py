import os
import tempfile
import unittest
from pathlib import Path

import server


class McpGatewayTest(unittest.TestCase):
    def test_gateway_exposes_both_mcp_endpoints(self):
        self.assertEqual({"/filesystem", "/web-search"}, set(server.SERVERS))
        self.assertEqual(
            ["filesystem.list_files", "filesystem.read_file"],
            [tool["name"] for tool in server.SERVERS["/filesystem"]["tools"]],
        )
        self.assertEqual("web_search", server.SERVERS["/web-search"]["tools"][0]["name"])

    def test_filesystem_read_file_is_routed_by_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("ok", encoding="utf-8")
            os.environ["ADA_FILESYSTEM_ALLOWED_ROOTS"] = tmp
            result = server.call_tool("/filesystem", "filesystem.read_file", {"path": str(path)})
            self.assertEqual("ok", result["content"])


if __name__ == "__main__":
    unittest.main()
