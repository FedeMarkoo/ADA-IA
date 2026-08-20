import unittest
import tempfile
from pathlib import Path

from ada.capabilities.system.run_script import run as script_run
from ada.infrastructure.runtime.resources import recommended_threads
from ada.infrastructure.integrations.gmail import send as gmail_send
from ada.capabilities.files.filesystem import run as filesystem_run
from ada.capabilities.files.group_files import run as group_files_run
from ada.capabilities.photography.organize_photos import run as organize_photos_run


class SecurityTests(unittest.TestCase):
    def test_filesystem_rejects_path_outside_allowlist(self):
        result = filesystem_run(
            {
                "action": "list_files",
                "dir": "/tmp",
                "allowed_roots": ["/Users/home/Desktop"],
            }
        )
        self.assertEqual(result["error"], "path_outside_allowed_roots")

    def test_scripts_are_disabled_without_explicit_allowlist(self):
        result = script_run({"command": "echo no"})
        self.assertEqual(result["error"], "command_execution_disabled")

    def test_thread_budget_scales_with_cpu_budget(self):
        self.assertGreaterEqual(recommended_threads({"cpu_limit_percent": 100}), 1)

    def test_filesystem_supports_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            (source / "file.txt").write_text("data")
            result = filesystem_run(
                {
                    "action": "move_files",
                    "source": source,
                    "name": "target",
                    "confirm": True,
                    "dry_run": True,
                    "allowed_roots": [directory],
                }
            )
            self.assertTrue(result["dry_run"])
            self.assertTrue((source / "file.txt").exists())
            self.assertFalse((Path(directory) / "target").exists())

    def test_gmail_send_returns_preview_before_side_effect(self):
        result = gmail_send({}, "fede@example.com", "Asunto", "Mensaje")
        self.assertEqual(result["error"], "confirmation_required")
        self.assertEqual(result["preview"]["to"], "fede@example.com")

    def test_filesystem_move_can_be_undone(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            item = source / "file.txt"
            item.write_text("data")
            moved = filesystem_run(
                {
                    "action": "move_files",
                    "source": source,
                    "name": "target",
                    "confirm": True,
                    "allowed_roots": [directory],
                }
            )
            self.assertFalse(item.exists())
            result = filesystem_run(
                {
                    "action": "undo",
                    "manifest": moved["changed"],
                    "confirm": True,
                    "allowed_roots": [directory],
                }
            )
            self.assertTrue(result["ok"])
            self.assertTrue(item.exists())

    def test_mutating_file_capabilities_require_scope_and_confirmation(self):
        self.assertEqual(group_files_run({"source": "/tmp", "name": "group"})["error"], "confirmation_required")
        self.assertEqual(organize_photos_run({"dir": "/tmp", "confirm": True})["error"], "allowed_roots_required")


if __name__ == "__main__":
    unittest.main()
