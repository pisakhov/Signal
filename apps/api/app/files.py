"""Sandboxed filesystem helpers for per-project folders."""
from pathlib import Path

from fastapi import HTTPException, status

from .settings import settings
from .utils import PROTECTED_FILES


# Maximum file size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


def project_dir(slug: str) -> Path:
    """Return the absolute path to the project's sandbox folder."""
    base = Path(settings.projects_root).resolve()
    path = (base / slug).resolve()
    if base not in path.parents and path != base:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid slug")
    return path


def resolve(slug: str, rel: str) -> Path:
    """Resolve a relative path inside the project, rejecting traversal."""
    root = project_dir(slug)
    target = (root / rel).resolve()
    if root != target and root not in target.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path escapes sandbox")
    return target


def list_tree(slug: str) -> list[dict]:
    """Return a flat listing of all files in the project sandbox."""
    root = project_dir(slug)
    if not root.exists():
        return []
    out: list[dict] = []
    for p in sorted(root.rglob("*")):
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        out.append(
            {
                "path": str(p.relative_to(root)),
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0,
            }
        )
    return out


def read_text(slug: str, rel: str) -> str:
    """Return the UTF-8 content of a file in the sandbox."""
    path = resolve(slug, rel)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    return path.read_text(encoding="utf-8")


def write_text(slug: str, rel: str, content: str) -> None:
    """Write UTF-8 content to a file, creating parents as needed."""
    # Check content size
    content_size = len(content.encode("utf-8"))
    if content_size > MAX_FILE_SIZE:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB)",
        )
    path = resolve(slug, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def delete(slug: str, rel: str) -> None:
    """Remove a file (no-op if missing)."""
    if rel in PROTECTED_FILES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"'{rel}' is protected"
        )
    path = resolve(slug, rel)
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path is a directory")


def rename(slug: str, rel_from: str, rel_to: str) -> None:
    """Rename a file within the sandbox."""
    if rel_from in PROTECTED_FILES or rel_to in PROTECTED_FILES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "dash_app.py is protected"
        )
    src = resolve(slug, rel_from)
    dst = resolve(slug, rel_to)
    if not src.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "source not found")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
