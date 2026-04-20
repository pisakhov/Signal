"""ADK tool functions scoped to a single project sandbox."""
import shlex
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List

from ..utils import (
    PROTECTED_FILES,
    BASH_WHITELIST,
    READONLY_BASH_WHITELIST,
    git_commit,
    get_current_commit,
)


def _resolve(root: Path, rel: str) -> Path:
    """Resolve a relative path inside `root`, rejecting escape attempts."""
    target = (root / rel).resolve()
    if root != target and root not in target.parents:
        raise ValueError("path escapes sandbox")
    return target


def make_tools(project_root: Path, slug: str) -> List[Callable]:
    """Build read/write/edit/bash tools pinned to a project dir and slug."""

    def read_file(path: str) -> Dict:
        """Return the UTF-8 text content of a file inside the project."""
        p = _resolve(project_root, path)
        if not p.is_file():
            return {"status": "error", "message": "not found"}
        return {"status": "success", "content": p.read_text(encoding="utf-8")}

    def write_file(path: str, content: str) -> Dict:
        """Create or overwrite a file with the given content."""
        p = _resolve(project_root, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        # Auto-commit to git
        commit_hash = git_commit(project_root, f"Agent: write {path}")
        response = {"status": "success", "path": path}
        if commit_hash:
            response["commit"] = commit_hash
        return response

    def edit_file(path: str, search: str, replace: str) -> Dict:
        """Replace the first occurrence of `search` with `replace` in a file."""
        p = _resolve(project_root, path)
        if not p.is_file():
            return {"status": "error", "message": "not found"}
        text = p.read_text(encoding="utf-8")
        if search not in text:
            return {"status": "error", "message": "search string not found"}
        p.write_text(text.replace(search, replace, 1), encoding="utf-8")
        # Auto-commit to git
        commit_hash = git_commit(project_root, f"Agent: edit {path}")
        response = {"status": "success", "path": path}
        if commit_hash:
            response["commit"] = commit_hash
        return response

    def bash(command: str) -> Dict:
        """Run a whitelisted shell command, or `redeploy` to restart the dashboard."""
        stripped = command.strip()
        if not stripped:
            return {
                "status": "error",
                "stdout": "",
                "stderr": "empty command",
                "exit_code": 2,
            }
        if any(ch in stripped for ch in ";&|><`$\n\r"):
            return {
                "status": "error",
                "stdout": "",
                "stderr": "shell metacharacters are not allowed",
                "exit_code": 2,
            }
        try:
            tokens = shlex.split(stripped)
        except ValueError as exc:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"parse error: {exc}",
                "exit_code": 2,
            }
        first = tokens[0]
        if first not in BASH_WHITELIST:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"command '{first}' not allowed; allowed: {sorted(BASH_WHITELIST)}",
                "exit_code": 126,
            }
        if first in {"rm", "mv"}:
            for arg in tokens[1:]:
                if Path(arg).name in PROTECTED_FILES:
                    return {
                        "status": "error",
                        "stdout": "",
                        "stderr": f"'{arg}' is protected and cannot be renamed or deleted",
                        "exit_code": 1,
                    }
        if first == "redeploy":
            from .. import runner
            from ..db import connect

            con = connect()
            row = con.execute(
                "SELECT id, port FROM projects WHERE slug = ?", [slug]
            ).fetchone()
            if row is None:
                con.close()
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": f"project with slug '{slug}' not found",
                    "exit_code": 1,
                }
            project_id, preferred = row
            try:
                port = runner.start(slug, preferred_port=preferred or None)
            except Exception as exc:
                con.close()
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": f"{type(exc).__name__}: {exc}",
                    "exit_code": 1,
                }
            con.execute(
                "UPDATE projects SET port = ?, current_commit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [port, get_current_commit(project_root), project_id],
            )
            con.close()
            time.sleep(1.5)
            if runner.status(slug) is None:
                tail = "\n".join(runner.logs(slug).splitlines()[-40:])
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": f"dashboard crashed on startup:\n{tail}",
                    "exit_code": 1,
                }
            return {
                "status": "success",
                "stdout": f"dashboard restarted on port {port}",
                "stderr": "",
                "exit_code": 0,
            }
        result = subprocess.run(
            tokens,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Auto-commit after file-modifying bash commands
        if result.returncode == 0 and first in {"rm", "mv", "cp", "touch", "mkdir"}:
            commit_msg = f"Agent: bash {first} {' '.join(tokens[1:])}"
            commit_hash = git_commit(project_root, commit_msg)
            response = {
                "status": "success",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
            if commit_hash:
                response["commit"] = commit_hash
            return response

        return {
            "status": "success" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }

    return [read_file, write_file, edit_file, bash]


def make_readonly_tools(project_root: Path) -> List[Callable]:
    """Build read-only tools for viewing published projects (no write/edit/bash)."""

    def read_file(path: str) -> Dict:
        """Return the UTF-8 text content of a file inside the project."""
        p = _resolve(project_root, path)
        if not p.is_file():
            return {"status": "error", "message": "not found"}
        return {"status": "success", "content": p.read_text(encoding="utf-8")}

    def bash(command: str) -> Dict:
        """Run a read-only whitelisted shell command for code exploration."""
        stripped = command.strip()
        if not stripped:
            return {
                "status": "error",
                "stdout": "",
                "stderr": "empty command",
                "exit_code": 2,
            }
        if any(ch in stripped for ch in ";&|><`$\n\r"):
            return {
                "status": "error",
                "stdout": "",
                "stderr": "shell metacharacters are not allowed",
                "exit_code": 2,
            }
        try:
            tokens = shlex.split(stripped)
        except ValueError as exc:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"parse error: {exc}",
                "exit_code": 2,
            }
        first = tokens[0]
        if first not in READONLY_BASH_WHITELIST:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"command '{first}' not allowed in read-only mode; allowed: {sorted(READONLY_BASH_WHITELIST)}",
                "exit_code": 126,
            }
        result = subprocess.run(
            tokens,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }

    return [read_file, bash]
