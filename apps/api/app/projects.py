"""Projects REST endpoints: list, create, publish, delete, files, redeploy."""
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from . import files as fs
from . import runner
from .auth import UserRow, current_user
from .db import connect
from .settings import settings
from .utils import git_commit, get_current_commit, ensure_git_repo, init_git_repo


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectOut(BaseModel):
    """Public view of a project row."""

    id: str
    owner_id: str
    owner_username: str
    title: str
    slug: str
    port: Optional[int]
    published: bool
    created_at: datetime
    updated_at: datetime
    owned_by_me: bool = False  # True if the current user is the owner


class CreateProjectIn(BaseModel):
    """Request payload for creating a project."""

    title: str


class RenameFileIn(BaseModel):
    """Request payload for renaming a file inside a project."""

    from_path: str
    to_path: str


class WriteFileIn(BaseModel):
    """Request payload for writing a file inside a project."""

    path: str
    content: str


class RevertIn(BaseModel):
    """Request payload for reverting to a historical commit."""

    commit: str


class HistoryEntry(BaseModel):
    """A single entry in the git history."""

    hash: str
    message: str
    author: str
    timestamp: str
    short_hash: str


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "project"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def _row_to_project(row, user_id: str | None = None) -> ProjectOut:
    return ProjectOut(
        id=row[0],
        owner_id=row[1],
        owner_username=row[2],
        title=row[3],
        slug=row[4],
        port=row[5],
        published=bool(row[6]),
        created_at=row[7],
        updated_at=row[8],
        owned_by_me=row[1] == user_id if user_id else False,
    )


_SELECT = (
    "SELECT p.id, p.owner_id, u.username, p.title, p.slug, p.port, p.published, "
    "p.created_at, p.updated_at FROM projects p JOIN users u ON u.id = p.owner_id"
)


@router.get("", response_model=list[ProjectOut])
def list_projects(user: UserRow = Depends(current_user)) -> list[ProjectOut]:
    """Return the caller's projects plus every published project."""
    con = connect()
    rows = con.execute(
        f"{_SELECT} WHERE p.owner_id = ? OR p.published = TRUE ORDER BY p.updated_at DESC",
        [user.id],
    ).fetchall()
    con.close()
    return [_row_to_project(r, user.id) for r in rows]


@router.post("", response_model=ProjectOut)
def create_project(
    body: CreateProjectIn, user: UserRow = Depends(current_user)
) -> ProjectOut:
    """Create a new project, copying the Dash template into its sandbox."""
    slug = _slugify(body.title)
    pid = str(uuid.uuid4())
    root = Path(settings.projects_root).resolve() / slug
    root.mkdir(parents=True, exist_ok=False)
    shutil.copy2(settings.template_dash, root / "dash_app.py")

    # Initialize git repo
    initial_commit = init_git_repo(root)

    con = connect()
    con.execute(
        "INSERT INTO projects (id, owner_id, title, slug, current_commit) VALUES (?, ?, ?, ?, ?)",
        [pid, user.id, body.title, slug, initial_commit],
    )
    row = con.execute(f"{_SELECT} WHERE p.id = ?", [pid]).fetchone()
    con.close()
    return _row_to_project(row, user.id)


def _require_owned(project_id: str, user: UserRow):
    con = connect()
    row = con.execute(f"{_SELECT} WHERE p.id = ?", [project_id]).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if row[1] != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your project")
    return row


def _require_viewable(project_id: str, user: UserRow):
    """Allow access if user is owner OR project is published."""
    con = connect()
    row = con.execute(f"{_SELECT} WHERE p.id = ?", [project_id]).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    is_owner = row[1] == user.id or user.is_admin
    is_published = bool(row[6])  # published column
    if not is_owner and not is_published:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "project not published")
    return row


@router.post("/{project_id}/publish", response_model=ProjectOut)
def publish(project_id: str, user: UserRow = Depends(current_user)) -> ProjectOut:
    """Toggle the published flag on a project you own."""
    row = _require_owned(project_id, user)
    con = connect()
    con.execute(
        "UPDATE projects SET published = NOT published, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [project_id],
    )
    row = con.execute(f"{_SELECT} WHERE p.id = ?", [project_id]).fetchone()
    con.close()
    return _row_to_project(row, user.id)


@router.delete("/{project_id}")
def delete_project(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Delete a project, its row, and its sandbox folder."""
    row = _require_owned(project_id, user)
    slug = row[4]
    runner.stop(slug)
    folder = Path(settings.projects_root).resolve() / slug
    if folder.exists():
        shutil.rmtree(folder)
    con = connect()
    con.execute("DELETE FROM projects WHERE id = ?", [project_id])
    con.close()
    return {"status": "ok"}


@router.get("/{project_id}/files")
def list_files(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """List files inside the project's sandbox."""
    row = _require_viewable(project_id, user)
    return {"items": fs.list_tree(row[4])}


@router.get("/{project_id}/file")
def read_file(
    project_id: str, path: str, user: UserRow = Depends(current_user)
) -> dict:
    """Read a single file as UTF-8 text."""
    row = _require_viewable(project_id, user)
    return {"path": path, "content": fs.read_text(row[4], path)}


@router.put("/{project_id}/file")
def write_file(
    project_id: str, body: WriteFileIn, user: UserRow = Depends(current_user)
) -> dict:
    """Create or overwrite a file with UTF-8 content."""
    row = _require_owned(project_id, user)
    slug = row[4]
    project_path = Path(settings.projects_root).resolve() / slug
    fs.write_text(slug, body.path, body.content)
    # Auto-commit git
    commit_hash = git_commit(project_path, f"Edit {body.path}")
    con = connect()
    con.execute(
        "UPDATE projects SET current_commit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [commit_hash, project_id],
    )
    con.close()
    return {"status": "ok"}


@router.post("/{project_id}/file/rename")
def rename_file(
    project_id: str, body: RenameFileIn, user: UserRow = Depends(current_user)
) -> dict:
    """Rename a file inside the sandbox."""
    row = _require_owned(project_id, user)
    slug = row[4]
    project_path = Path(settings.projects_root).resolve() / slug
    fs.rename(slug, body.from_path, body.to_path)
    # Auto-commit git
    commit_hash = git_commit(project_path, f"Rename {body.from_path} to {body.to_path}")
    con = connect()
    con.execute(
        "UPDATE projects SET current_commit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [commit_hash, project_id],
    )
    con.close()
    return {"status": "ok"}


@router.delete("/{project_id}/file")
def delete_file(
    project_id: str, path: str, user: UserRow = Depends(current_user)
) -> dict:
    """Delete a file inside the sandbox."""
    row = _require_owned(project_id, user)
    slug = row[4]
    project_path = Path(settings.projects_root).resolve() / slug
    fs.delete(slug, path)
    # Auto-commit git
    commit_hash = git_commit(project_path, f"Delete {path}")
    con = connect()
    con.execute(
        "UPDATE projects SET current_commit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [commit_hash, project_id],
    )
    con.close()
    return {"status": "ok"}


@router.post("/{project_id}/redeploy")
def redeploy(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Restart the project's Dash subprocess and persist its port."""
    row = _require_owned(project_id, user)
    slug = row[4]
    project_path = Path(settings.projects_root).resolve() / slug
    port = runner.start(slug, preferred_port=row[5] or None)
    con = connect()
    con.execute(
        "UPDATE projects SET port = ?, current_commit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [port, get_current_commit(project_path), project_id],
    )
    con.close()
    return {"port": port}


@router.post("/{project_id}/stop")
def stop(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Stop the project's Dash subprocess."""
    row = _require_owned(project_id, user)
    runner.stop(row[4])
    return {"status": "stopped"}


@router.post("/{project_id}/start")
def start(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Start a published project's Dash subprocess (for viewing)."""
    row = _require_viewable(project_id, user)
    slug = row[4]
    project_path = Path(settings.projects_root).resolve() / slug

    # Only start if not already running
    existing_port = runner.status(slug)
    if existing_port:
        return {"port": existing_port}

    port = runner.start(slug, preferred_port=row[5] or None)
    con = connect()
    con.execute(
        "UPDATE projects SET port = ?, current_commit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [port, get_current_commit(project_path), project_id],
    )
    con.close()
    return {"port": port}


@router.get("/{project_id}/logs")
def get_logs(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Return the captured stdout+stderr of the project's Dash subprocess."""
    row = _require_viewable(project_id, user)
    return {"text": runner.logs(row[4]), "running": runner.status(row[4]) is not None}


@router.get("/{project_id}/history", response_model=list[HistoryEntry])
def get_history(project_id: str, user: UserRow = Depends(current_user)) -> list[HistoryEntry]:
    """Return git commit history for a project."""
    row = _require_viewable(project_id, user)
    project_path = Path(settings.projects_root).resolve() / row[4]

    # Ensure git repo exists
    ensure_git_repo(project_path)

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--pretty=format:%H|%s|%an|%ai",
                "--abbrev-commit",
            ],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        entries: list[HistoryEntry] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                full_hash, message, author, timestamp = parts[0], parts[1], parts[2], parts[3]
                short_hash = full_hash[:7]
                entries.append(
                    HistoryEntry(
                        hash=full_hash,
                        short_hash=short_hash,
                        message=message,
                        author=author,
                        timestamp=timestamp,
                    )
                )
        return entries
    except Exception:
        return []


@router.post("/{project_id}/revert")
def revert_to_commit(
    project_id: str, body: RevertIn, user: UserRow = Depends(current_user)
) -> dict:
    """Revert the project to a specific git commit."""
    row = _require_owned(project_id, user)
    slug = row[4]
    project_path = Path(settings.projects_root).resolve() / slug

    git_dir = project_path / ".git"
    if not git_dir.exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No git history found")

    try:
        # Checkout the specific commit
        result = subprocess.run(
            ["git", "checkout", body.commit],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Git checkout failed: {result.stderr}",
            )

        # Get the current commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )

        current_hash = (
            commit_result.stdout.strip() if commit_result.returncode == 0 else None
        )

        # Update database with new commit
        con = connect()
        con.execute(
            "UPDATE projects SET current_commit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [current_hash, project_id],
        )
        con.close()

        # Restart the dash process
        port = runner.start(slug, preferred_port=row[5] or None)

        return {
            "status": "ok",
            "commit": current_hash,
            "port": port,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Revert failed: {str(e)}",
        )


@router.post("/{project_id}/fork", response_model=ProjectOut)
def fork_project(
    project_id: str, user: UserRow = Depends(current_user)
) -> ProjectOut:
    """Create a copy of a project as a new project owned by the user.

    - Published projects can be forked by anyone
    - Your own projects can be duplicated (forked by yourself)
    """
    con = connect()
    row = con.execute(f"{_SELECT} WHERE p.id = ?", [project_id]).fetchone()
    con.close()

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")

    project_out = _row_to_project(row, user.id)

    # Must be owner OR project must be published
    is_owner = project_out.owner_id == user.id
    if not is_owner and not project_out.published:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Can only fork published projects",
        )

    source_slug = project_out.slug
    source_path = Path(settings.projects_root).resolve() / source_slug

    # Create new project - "copy" for own projects, "fork" for others
    suffix = "copy" if is_owner else "fork"
    new_title = f"{project_out.title} ({suffix})"
    new_slug = _slugify(new_title)
    new_pid = str(uuid.uuid4())
    new_path = Path(settings.projects_root).resolve() / new_slug

    # Copy the project directory
    try:
        shutil.copytree(source_path, new_path)
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Failed to copy project: {str(e)}",
        )

    # Initialize fresh git repo for the fork
    # Different commit message for copy vs fork
    if is_owner:
        commit_message = f"Copy of {project_out.title}"
    else:
        commit_message = f"Forked from {project_out.owner_username}/{project_out.title}"

    # Remove existing .git if present and initialize fresh git repo
    existing_git = new_path / ".git"
    if existing_git.exists():
        shutil.rmtree(existing_git)
    initial_commit = init_git_repo(new_path, commit_message)

    # Create database record
    con = connect()
    con.execute(
        "INSERT INTO projects (id, owner_id, title, slug, current_commit) VALUES (?, ?, ?, ?, ?)",
        [new_pid, user.id, new_title, new_slug, initial_commit],
    )
    new_row = con.execute(f"{_SELECT} WHERE p.id = ?", [new_pid]).fetchone()
    con.close()

    return _row_to_project(new_row, user.id)
