import os
import tempfile
import unittest
from pathlib import Path

import server


class FilesystemMcpServerTest(unittest.TestCase):
    def test_list_files_is_non_recursive_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "top.txt").write_text("top")
            (root / "nested").mkdir()
            (root / "nested" / "deep.txt").write_text("deep")
            os.environ["ADA_FILESYSTEM_ALLOWED_ROOTS"] = tmp
            result = server.list_files({"path": tmp})
            self.assertEqual(result["total_items"], 2)
            self.assertFalse(result["recursive"])

    def test_path_outside_allowlist_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ADA_FILESYSTEM_ALLOWED_ROOTS"] = tmp
            with self.assertRaises(PermissionError):
                server.list_files({"path": "/"})

    def test_tools_list_advertises_contract(self):
        self.assertEqual(server.TOOL["name"], "filesystem.list_files")
        self.assertEqual(server.TOOL["inputSchema"]["required"], ["path"])
        self.assertEqual(server.READ_FILE_TOOL["name"], "filesystem.read_file")

    def test_read_file_returns_text_within_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("hola ADA", encoding="utf-8")
            os.environ["ADA_FILESYSTEM_ALLOWED_ROOTS"] = tmp
            result = server.read_file({"path": str(path)})
            self.assertEqual(result["content"], "hola ADA")
            self.assertEqual(result["size_bytes"], 8)

    def test_read_file_rejects_large_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.txt"
            path.write_text("abcdef", encoding="utf-8")
            os.environ["ADA_FILESYSTEM_ALLOWED_ROOTS"] = tmp
            result = server.read_file({"path": str(path), "max_bytes": 3})
            self.assertEqual(result["error"], "file_too_large")


if __name__ == "__main__":
    unittest.main()
