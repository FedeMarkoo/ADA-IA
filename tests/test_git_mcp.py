import unittest
from unittest.mock import MagicMock, patch

from mcps.git.manager import GitManager
from mcps.git.server import create_git_server
from ada.mcps.manager import MCPManager
from ada.capabilities.data.git import run as git_capability_run


class TestGitMCP(unittest.TestCase):
    def test_git_manager_status_success(self):
        mgr = GitManager()
        fake_porcelain = "## main...origin/main\n M ada/config.py\n?? new_file.py\nM  staged.py\n"
        with patch.object(mgr, "_run_git", return_value={"ok": True, "exit_code": 0, "stdout": fake_porcelain, "stderr": ""}):
            res = mgr.status()
            self.assertTrue(res["ok"])
            self.assertEqual(res["branch"], "main")
            self.assertFalse(res["is_clean"])
            self.assertEqual(len(res["staged"]), 1)
            self.assertEqual(res["staged"][0]["file"], "staged.py")
            self.assertEqual(len(res["unstaged"]), 1)
            self.assertEqual(res["unstaged"][0]["file"], "ada/config.py")
            self.assertEqual(len(res["untracked"]), 1)
            self.assertEqual(res["untracked"][0], "new_file.py")

    def test_git_manager_log(self):
        mgr = GitManager()
        fake_log = "a1b2c3d|Federico|fede@example.com|2026-08-20|Initial commit\n"
        with patch.object(mgr, "_run_git", return_value={"ok": True, "exit_code": 0, "stdout": fake_log, "stderr": ""}):
            res = mgr.log({"limit": 5})
            self.assertTrue(res["ok"])
            self.assertEqual(res["count"], 1)
            self.assertEqual(res["commits"][0]["hash"], "a1b2c3d")
            self.assertEqual(res["commits"][0]["author"], "Federico")
            self.assertEqual(res["commits"][0]["message"], "Initial commit")

    def test_git_manager_commit_validation(self):
        mgr = GitManager()
        res = mgr.commit({"message": ""})
        self.assertFalse(res["ok"])
        self.assertIn("no puede estar vacío", res["error"])

    def test_git_server_tools_registered(self):
        server = create_git_server()
        for tool in ("git.status", "git.log", "git.diff", "git.add", "git.commit", "git.branch", "git.push", "git.pull"):
            self.assertIn(tool, server.tools)

    def test_mcp_manager_discovers_git_tools(self):
        manager = MCPManager()
        tools = manager.list_tools(category="git")
        tool_names = [t["name"] for t in tools]
        self.assertIn("git.status", tool_names)
        self.assertIn("git.commit", tool_names)

    def test_git_capability_run(self):
        with patch("ada.capabilities.data.git.GitManager.status", return_value={"ok": True, "branch": "main"}):
            res = git_capability_run({"action": "status"})
            self.assertTrue(res["ok"])
            self.assertEqual(res["branch"], "main")


if __name__ == "__main__":
    unittest.main()
