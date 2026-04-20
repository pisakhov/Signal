"""Shared utilities for git operations and security constants."""
import os
import subprocess
from pathlib import Path
from typing import Optional


# Protected files that cannot be deleted or renamed
PROTECTED_FILES = {"dash_app.py", ".git", ".gitignore"}


# Full bash command whitelist for owners
BASH_WHITELIST = {
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "grep",
    "rg",
    "find",
    "tree",
    "wc",
    "which",
    "echo",
    "touch",
    "mkdir",
    "mv",
    "cp",
    "rm",
    "redeploy",
    "uv",
    "git",
}


# Read-only bash whitelist for non-owners (subset of full whitelist)
READONLY_BASH_WHITELIST = {
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "grep",
    "rg",
    "find",
    "tree",
    "wc",
    "which",
    "echo",
}


def git_commit(
    project_path: Path,
    message: str,
    author_name: str = "Signal",
    author_email: str = "signal@local",
) -> Optional[str]:
    """Commit changes to git, returning the commit hash or None on failure."""
    git_dir = project_path / ".git"
    if not git_dir.exists():
        return None
    try:
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if not result.stdout.strip():
            return None  # No changes
        # Add all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(project_path),
            capture_output=True,
            timeout=10,
        )
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": author_name,
                "GIT_AUTHOR_EMAIL": author_email,
                "GIT_COMMITTER_NAME": author_name,
                "GIT_COMMITTER_EMAIL": author_email,
            },
        )
        if result.returncode == 0:
            # Get the commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        return None
    except Exception:
        return None


def get_current_commit(project_path: Path) -> Optional[str]:
    """Get the current HEAD commit hash, or None if not a git repo."""
    git_dir = project_path / ".git"
    if not git_dir.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def init_git_repo(project_path: Path, commit_message: str = "Initial commit") -> str | None:
    """Initialize a git repo and return the initial commit hash, or None on failure.

    Args:
        project_path: Path to the project directory
        commit_message: Commit message for the initial commit (default: "Initial commit")
    """
    try:
        subprocess.run(
            ["git", "init"],
            cwd=str(project_path),
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "config", "user.name", "Signal"],
            cwd=str(project_path),
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "config", "user.email", "signal@local"],
            cwd=str(project_path),
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(project_path),
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=str(project_path),
            capture_output=True,
            timeout=10,
        )
        # Get the commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def ensure_git_repo(project_path: Path) -> bool:
    """Initialize a git repo if one doesn't exist."""
    git_dir = project_path / ".git"
    if not git_dir.exists():
        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(project_path),
                capture_output=True,
                timeout=10,
            )
            # Configure git user
            subprocess.run(
                ["git", "config", "user.name", "Signal"],
                cwd=str(project_path),
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "config", "user.email", "signal@local"],
                cwd=str(project_path),
                capture_output=True,
                timeout=10,
            )
            # Create initial commit
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(project_path),
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=str(project_path),
                capture_output=True,
                timeout=10,
            )
            return True
        except Exception:
            return False
    return True
