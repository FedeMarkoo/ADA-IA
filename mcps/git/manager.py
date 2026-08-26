"""Git operations manager for ADA MCP."""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class GitManager:
    """Safely executes and parses Git operations."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path).resolve() if repo_path else Path.cwd()

    def _run_git(self, args: List[str], timeout: int = 15) -> Dict[str, Any]:
        """Execute a git command with environment variables and safe execution."""
        env = os.environ.copy()
        local_git_core = Path.home() / ".local/usr/lib/git-core"
        local_git_templates = Path.home() / ".local/usr/share/git-core/templates"
        if "GIT_EXEC_PATH" not in env and local_git_core.exists():
            env["GIT_EXEC_PATH"] = str(local_git_core)
        if "GIT_TEMPLATE_DIR" not in env and local_git_templates.exists():
            env["GIT_TEMPLATE_DIR"] = str(local_git_templates)

        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
            )
            return {
                "ok": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Comando git {' '.join(args)} excedió el tiempo límite ({timeout}s)"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def status(self, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get structured git repository status."""
        res = self._run_git(["status", "--porcelain=v1", "-b"])
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        lines = res["stdout"].splitlines()
        branch_info = lines[0] if lines else "## No branch"
        branch_name = branch_info.replace("## ", "").split("...")[0]

        staged: List[Dict[str, str]] = []
        unstaged: List[Dict[str, str]] = []
        untracked: List[str] = []

        for line in lines[1:]:
            if len(line) < 3:
                continue
            index_code = line[0]
            work_code = line[1]
            filepath = line[3:].strip()

            if index_code == "?" and work_code == "?":
                untracked.append(filepath)
            else:
                if index_code != " " and index_code != "?":
                    staged.append({"status": index_code, "file": filepath})
                if work_code != " " and work_code != "?":
                    unstaged.append({"status": work_code, "file": filepath})

        return {
            "ok": True,
            "branch": branch_name,
            "is_clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0,
            "staged_count": len(staged),
            "unstaged_count": len(unstaged),
            "untracked_count": len(untracked),
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "raw": res["stdout"],
        }

    def log(self, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get git commit history."""
        args = args or {}
        limit = int(args.get("limit", 10))
        res = self._run_git(["log", f"-n{limit}", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=short"])
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        commits = []
        for line in res["stdout"].splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append(
                    {
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    }
                )

        return {"ok": True, "count": len(commits), "commits": commits}

    def diff(self, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get git diff for working tree or staged changes."""
        args = args or {}
        staged = bool(args.get("staged", False))
        file_path = args.get("file")

        cmd = ["diff"]
        if staged:
            cmd.append("--staged")
        if file_path:
            cmd.extend(["--", file_path])

        res = self._run_git(cmd)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        return {"ok": True, "staged": staged, "diff": res["stdout"]}

    def add(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Stage files for commit."""
        files = args.get("files", ["."])
        if isinstance(files, str):
            files = [files]

        # End git options before accepting user-controlled paths.
        cmd = ["add", "--"] + files
        res = self._run_git(cmd)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        return {"ok": True, "message": f"Archivos agregados al stage: {', '.join(files)}"}

    def commit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Commit staged changes."""
        message = args.get("message", "").strip()
        if not message:
            return {"ok": False, "error": "El mensaje de commit no puede estar vacío."}

        cmd = ["commit", "-m", message]
        res = self._run_git(cmd)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        return {"ok": True, "output": res["stdout"], "message": message}

    def branch(self, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List branches or create a new branch."""
        args = args or {}
        new_branch = args.get("create")
        if new_branch:
            res = self._run_git(["branch", new_branch])
            if not res.get("ok"):
                return {"ok": False, "error": res.get("stderr") or res.get("error")}
            return {"ok": True, "message": f"Rama '{new_branch}' creada con éxito."}

        res = self._run_git(["branch", "-a"])
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        branches = [b.strip() for b in res["stdout"].splitlines() if b.strip()]
        return {"ok": True, "branches": branches}

    def push(self, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Push changes to remote repository."""
        args = args or {}
        remote = args.get("remote", "origin")
        branch_name = args.get("branch", "main")
        set_upstream = bool(args.get("set_upstream", False))

        cmd = ["push"]
        if set_upstream:
            cmd.append("-u")
        cmd.extend([remote, branch_name])

        res = self._run_git(cmd, timeout=30)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        return {"ok": True, "output": res["stdout"] or res["stderr"], "remote": remote, "branch": branch_name}

    def pull(self, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Pull latest changes from remote repository."""
        args = args or {}
        remote = args.get("remote", "origin")
        branch_name = args.get("branch", "main")

        cmd = ["pull", remote, branch_name]
        res = self._run_git(cmd, timeout=30)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("stderr") or res.get("error")}

        return {"ok": True, "output": res["stdout"] or res["stderr"]}
