import tempfile
import unittest
from pathlib import Path

from mcps.filesystem.handlers import FilesystemHandlers
from mcps.filesystem.server import create_filesystem_server


class FilesystemMCPTests(unittest.TestCase):
    def test_empty_allowlist_denies_filesystem_access(self):
        handlers = FilesystemHandlers([])
        with self.assertRaises(PermissionError):
            handlers.check_path("/tmp")

    def test_read_file_rejects_content_above_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.txt"
            path.write_text("abcdef")
            result = FilesystemHandlers([tmp]).read_file({"path": str(path), "max_bytes": 3})
            self.assertEqual(result["error"], "file_too_large")

    def test_list_files_is_non_recursive_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "top.txt").write_text("top")
            (root / "nested").mkdir()
            (root / "nested" / "deep.txt").write_text("deep")

            result = FilesystemHandlers([tmp]).list_files({"path": tmp})

            self.assertFalse(result["recursive"])
            self.assertEqual(result["total_items"], 2)
            self.assertEqual({item["name"] for item in result["items"]}, {"top.txt", "nested"})

    def test_list_files_can_be_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "top.txt").write_text("top")
            (root / "nested").mkdir()
            (root / "nested" / "deep.txt").write_text("deep")

            result = FilesystemHandlers([tmp]).list_files({"path": tmp, "recursive": True})

            self.assertTrue(result["recursive"])
            self.assertEqual(result["total_items"], 3)
            self.assertIn("nested/deep.txt", {item["name"] for item in result["items"]})

    def test_mcp_schema_exposes_recursive_default_false(self):
        server = create_filesystem_server([tempfile.gettempdir()])
        tool = server.tools["filesystem.list_files"]
        schema = tool["inputSchema"]

        self.assertEqual(schema["properties"]["recursive"]["type"], "boolean")
        self.assertFalse(schema["properties"]["recursive"]["default"])
        self.assertEqual(schema["required"], ["path"])

    def test_photo_summary_hides_technical_extensions(self):
        self.assertEqual(
            FilesystemHandlers.photo_summary({"xml": 300, "raw": 300, "jpg": 300}),
            "300 fotos aceptadas y exportadas",
        )
        self.assertEqual(
            FilesystemHandlers.photo_summary({"xml": 300, "raw": 300, "jpg": 0}),
            "300 fotos aceptadas sin exportar",
        )


if __name__ == "__main__":
    unittest.main()
