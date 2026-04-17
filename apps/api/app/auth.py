"""JWT + bcrypt authentication primitives."""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from jose import jwt, JWTError
from pydantic import BaseModel

from .db import connect
from .settings import settings


ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24 * 7
BCRYPT_MAX_BYTES = 72


class UserRow(BaseModel):
    """Public user shape used across the API."""

    id: str
    username: str
    is_admin: bool


def _encode(plain: str) -> bytes:
    """Encode a password to bytes, truncating to bcrypt's 72-byte limit."""
    return plain.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Return a bcrypt hash for the given plaintext."""
    return bcrypt.hashpw(_encode(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compare plaintext against a stored bcrypt hash."""
    return bcrypt.checkpw(_encode(plain), hashed.encode("utf-8"))


def create_token(user_id: str) -> str:
    """Sign a JWT carrying the user id and expiry."""
    payload = {
        "sub": user_id,
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=ALGORITHM)


def _decode(token: str) -> str:
    try:
        data = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
        return data["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")


def ensure_admin_seed() -> None:
    """Create the admin user on first boot if env credentials are set."""
    if not settings.admin_password:
        return
    con = connect()
    row = con.execute(
        "SELECT id FROM users WHERE username = ?", [settings.admin_username]
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO users (id, username, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                settings.admin_username,
                hash_password(settings.admin_password),
                True,
            ],
        )
    con.close()


def current_user(request: Request) -> UserRow:
    """FastAPI dependency resolving the caller from the `Authorization` header."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    user_id = _decode(header.split(" ", 1)[1])
    con = connect()
    row = con.execute(
        "SELECT id, username, is_admin FROM users WHERE id = ?", [user_id]
    ).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return UserRow(id=row[0], username=row[1], is_admin=bool(row[2]))


def require_admin(user: UserRow = Depends(current_user)) -> UserRow:
    """Dependency that rejects non-admin callers."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return user


def authenticate(username: str, password: str) -> Optional[UserRow]:
    """Return a user if the credentials are valid, else None."""
    con = connect()
    row = con.execute(
        "SELECT id, username, password_hash, is_admin FROM users WHERE username = ?",
        [username],
    ).fetchone()
    con.close()
    if row is None or not verify_password(password, row[2]):
        return None
    return UserRow(id=row[0], username=row[1], is_admin=bool(row[3]))
