"""Projects REST endpoints: list, create, publish, delete, files, redeploy."""
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from . import files as fs
from . import runner
from .auth import UserRow, current_user
from .db import connect
from .settings import settings


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


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "project"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def _row_to_project(row) -> ProjectOut:
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
    )


_SELECT = (
    "SELECT p.id, p.owner_id, u.username, p.title, p.slug, p.port, p.published, "
    "p.created_at, p.updated_at FROM projects p JOIN users u ON u.id = p.owner_id"
)


@router.get("", response_model=List[ProjectOut])
def list_projects(user: UserRow = Depends(current_user)) -> List[ProjectOut]:
    """Return the caller's projects plus every published project."""
    con = connect()
    rows = con.execute(
        f"{_SELECT} WHERE p.owner_id = ? OR p.published = TRUE ORDER BY p.updated_at DESC",
        [user.id],
    ).fetchall()
    con.close()
    return [_row_to_project(r) for r in rows]


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
    con = connect()
    con.execute(
        "INSERT INTO projects (id, owner_id, title, slug) VALUES (?, ?, ?, ?)",
        [pid, user.id, body.title, slug],
    )
    row = con.execute(f"{_SELECT} WHERE p.id = ?", [pid]).fetchone()
    con.close()
    return _row_to_project(row)


def _require_owned(project_id: str, user: UserRow):
    con = connect()
    row = con.execute(f"{_SELECT} WHERE p.id = ?", [project_id]).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if row[1] != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your project")
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
    return _row_to_project(row)


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
    row = _require_owned(project_id, user)
    return {"items": fs.list_tree(row[4])}


@router.get("/{project_id}/file")
def read_file(
    project_id: str, path: str, user: UserRow = Depends(current_user)
) -> dict:
    """Read a single file as UTF-8 text."""
    row = _require_owned(project_id, user)
    return {"path": path, "content": fs.read_text(row[4], path)}


@router.put("/{project_id}/file")
def write_file(
    project_id: str, body: WriteFileIn, user: UserRow = Depends(current_user)
) -> dict:
    """Create or overwrite a file with UTF-8 content."""
    row = _require_owned(project_id, user)
    fs.write_text(row[4], body.path, body.content)
    con = connect()
    con.execute(
        "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [project_id],
    )
    con.close()
    return {"status": "ok"}


@router.post("/{project_id}/file/rename")
def rename_file(
    project_id: str, body: RenameFileIn, user: UserRow = Depends(current_user)
) -> dict:
    """Rename a file inside the sandbox."""
    row = _require_owned(project_id, user)
    fs.rename(row[4], body.from_path, body.to_path)
    return {"status": "ok"}


@router.delete("/{project_id}/file")
def delete_file(
    project_id: str, path: str, user: UserRow = Depends(current_user)
) -> dict:
    """Delete a file inside the sandbox."""
    row = _require_owned(project_id, user)
    fs.delete(row[4], path)
    return {"status": "ok"}


@router.post("/{project_id}/redeploy")
def redeploy(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Restart the project's Dash subprocess and persist its port."""
    row = _require_owned(project_id, user)
    port = runner.start(row[4], preferred_port=row[5] or None)
    con = connect()
    con.execute(
        "UPDATE projects SET port = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [port, project_id],
    )
    con.close()
    return {"port": port}


@router.post("/{project_id}/stop")
def stop(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Stop the project's Dash subprocess."""
    row = _require_owned(project_id, user)
    runner.stop(row[4])
    return {"status": "stopped"}


@router.get("/{project_id}/logs")
def get_logs(project_id: str, user: UserRow = Depends(current_user)) -> dict:
    """Return the captured stdout+stderr of the project's Dash subprocess."""
    row = _require_owned(project_id, user)
    return {"text": runner.logs(row[4]), "running": runner.status(row[4]) is not None}
