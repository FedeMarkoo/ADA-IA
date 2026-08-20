import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ada.capabilities.photography import lightroom
from ada.interfaces.lightroom_mcp_server import TOOL_SCHEMAS, _tools


class LightroomMcpTests(unittest.TestCase):
    def test_exposes_safe_and_mutating_tools(self):
        tools = _tools()
        self.assertEqual(
            set(tools),
            {
                "lightroom_count_photos",
                "lightroom_analyze",
                "lightroom_plan",
                "lightroom_simulate",
                "lightroom_apply",
                "lightroom_recover",
            },
        )

    def test_mutating_tools_require_explicit_confirmation(self):
        self.assertEqual(TOOL_SCHEMAS["lightroom_apply"]["required"], ["confirm"])
        self.assertEqual(TOOL_SCHEMAS["lightroom_apply"]["properties"]["confirm"]["const"], True)
        self.assertEqual(TOOL_SCHEMAS["lightroom_recover"]["required"], ["confirm"])

    def test_read_only_tools_do_not_require_confirmation(self):
        for name in ("lightroom_count_photos", "lightroom_analyze", "lightroom_plan", "lightroom_simulate"):
            self.assertNotIn("required", TOOL_SCHEMAS[name])

    def test_server_rejects_paths_outside_its_own_allowlist_and_audits_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "manager.py"
            script.write_text("", encoding="utf-8")
            audit = MagicMock()
            tools = _tools(
                {
                    "allowed_roots": [str(root)],
                    "lightroom_script": str(script),
                    "lightroom_db": str(root / "lightroom.sqlite3"),
                },
                audit,
            )
            result = tools["lightroom_plan"]({"root": str(root.parent / "outside")})
        self.assertEqual(result["error"], "path_outside_allowed_roots")
        audit.record_audit.assert_called_once()
        self.assertFalse(audit.record_audit.call_args.kwargs["success"])

    def test_server_rejects_an_unlisted_script_even_inside_an_allowed_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configured = root / "configured.py"
            untrusted = root / "untrusted.py"
            configured.write_text("", encoding="utf-8")
            untrusted.write_text("", encoding="utf-8")
            tools = _tools(
                {
                    "allowed_roots": [str(root)],
                    "lightroom_allowed_scripts": [str(configured)],
                    "lightroom_db": str(root / "lightroom.sqlite3"),
                }
            )
            result = tools["lightroom_plan"]({"root": str(root), "script": str(untrusted)})
        self.assertEqual(result["error"], "lightroom_script_not_allowed")

    def test_server_fails_closed_without_allowed_roots(self):
        tools = _tools({"allowed_roots": [], "lightroom_allowed_scripts": []})
        result = tools["lightroom_plan"]({"root": "/tmp"})
        self.assertEqual(result["error"], "allowed_roots_required")

    def test_server_uses_canonical_adapter_and_audits_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "manager.py"
            script.write_text("", encoding="utf-8")
            audit = MagicMock()
            tools = _tools(
                {
                    "allowed_roots": [str(root)],
                    "lightroom_script": str(script),
                    "lightroom_db": str(root / "lightroom.sqlite3"),
                },
                audit,
            )
            with patch.object(lightroom, "_run", return_value={"ok": True, "returncode": 0}):
                result = tools["lightroom_plan"]({"root": str(root)})
        self.assertTrue(result["ok"])
        audit.record_audit.assert_called_once()
        self.assertTrue(audit.record_audit.call_args.kwargs["success"])

    def test_server_audits_nonzero_subprocess_result_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "manager.py"
            script.write_text("", encoding="utf-8")
            audit = MagicMock()
            tools = _tools(
                {
                    "allowed_roots": [str(root)],
                    "lightroom_script": str(script),
                    "lightroom_db": str(root / "lightroom.sqlite3"),
                },
                audit,
            )
            with patch.object(lightroom, "_run", return_value={"ok": False, "returncode": 2}):
                result = tools["lightroom_plan"]({"root": str(root)})
        self.assertFalse(result["ok"])
        self.assertFalse(audit.record_audit.call_args.kwargs["success"])

    def test_server_bounds_subprocess_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "manager.py"
            script.write_text("", encoding="utf-8")
            tools = _tools(
                {
                    "allowed_roots": [str(root)],
                    "lightroom_script": str(script),
                    "lightroom_db": str(root / "lightroom.sqlite3"),
                    "lightroom_mcp_max_timeout": 30,
                }
            )
            result = tools["lightroom_plan"]({"root": str(root), "timeout": 31})
        self.assertEqual(result, {"error": "invalid_lightroom_timeout", "maximum": 30})

    def test_adapter_reports_subprocess_timeout_and_start_errors(self):
        timeout = subprocess.TimeoutExpired(["python", "manager.py"], 3, output="partial", stderr="slow")
        with patch.object(lightroom.subprocess, "run", side_effect=timeout):
            result = lightroom._run(["python", "manager.py"], timeout=3)
        self.assertEqual(result["error"], "lightroom_timeout")
        self.assertEqual(result["stdout"], "partial")

        with patch.object(lightroom.subprocess, "run", side_effect=OSError("missing")):
            result = lightroom._run(["missing"], timeout=3)
        self.assertEqual(result["error"], "lightroom_process_start_failed")


if __name__ == "__main__":
    unittest.main()
