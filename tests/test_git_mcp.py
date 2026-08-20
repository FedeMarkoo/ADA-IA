"""Unit tests for Git MCP Server and ADA Git Capability."""

import pytest
from unittest.mock import MagicMock, patch
from mcps.git.manager import GitManager
from mcps.git.server import create_git_server
from ada.mcps.manager import MCPManager
from ada.capabilities.data.git import run as git_capability_run


def test_git_manager_status_success():
    mgr = GitManager()
    fake_porcelain = "## main...origin/main\n M ada/config.py\n?? new_file.py\nM  staged.py\n"
    with patch.object(mgr, "_run_git", return_value={"ok": True, "exit_code": 0, "stdout": fake_porcelain, "stderr": ""}):
        res = mgr.status()
        assert res["ok"] is True
        assert res["branch"] == "main"
        assert res["is_clean"] is False
        assert len(res["staged"]) == 1
        assert res["staged"][0]["file"] == "staged.py"
        assert len(res["unstaged"]) == 1
        assert res["unstaged"][0]["file"] == "ada/config.py"
        assert len(res["untracked"]) == 1
        assert res["untracked"][0] == "new_file.py"


def test_git_manager_log():
    mgr = GitManager()
    fake_log = "a1b2c3d|Federico|fede@example.com|2026-08-20|Initial commit\n"
    with patch.object(mgr, "_run_git", return_value={"ok": True, "exit_code": 0, "stdout": fake_log, "stderr": ""}):
        res = mgr.log({"limit": 5})
        assert res["ok"] is True
        assert res["count"] == 1
        assert res["commits"][0]["hash"] == "a1b2c3d"
        assert res["commits"][0]["author"] == "Federico"
        assert res["commits"][0]["message"] == "Initial commit"


def test_git_manager_commit_validation():
    mgr = GitManager()
    res = mgr.commit({"message": ""})
    assert res["ok"] is False
    assert "no puede estar vacío" in res["error"]


def test_git_server_tools_registered():
    server = create_git_server()
    assert "git.status" in server.tools
    assert "git.log" in server.tools
    assert "git.diff" in server.tools
    assert "git.add" in server.tools
    assert "git.commit" in server.tools
    assert "git.branch" in server.tools
    assert "git.push" in server.tools
    assert "git.pull" in server.tools


def test_mcp_manager_discovers_git_tools():
    manager = MCPManager()
    tools = manager.list_tools(category="git")
    tool_names = [t["name"] for t in tools]
    assert "git.status" in tool_names
    assert "git.commit" in tool_names


def test_git_capability_run():
    with patch("ada.capabilities.data.git.GitManager.status", return_value={"ok": True, "branch": "main"}):
        res = git_capability_run({"action": "status"})
        assert res["ok"] is True
        assert res["branch"] == "main"
