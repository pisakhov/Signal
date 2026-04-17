"""Auth endpoints: login + admin user creation."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import (
    UserRow,
    authenticate,
    create_token,
    current_user,
    hash_password,
    require_admin,
)
from .db import connect


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    """Credentials payload."""

    username: str
    password: str


class CreateUserIn(BaseModel):
    """Admin-only user creation payload."""

    username: str
    password: str
    is_admin: bool = False


class LoginOut(BaseModel):
    """Token + user shape returned on successful login."""

    token: str
    user: UserRow


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn) -> LoginOut:
    """Exchange credentials for a JWT."""
    user = authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return LoginOut(token=create_token(user.id), user=user)


@router.get("/me", response_model=UserRow)
def me(user: UserRow = Depends(current_user)) -> UserRow:
    """Return the caller's user row."""
    return user


@router.post("/users", response_model=UserRow)
def create_user(
    body: CreateUserIn, _admin: UserRow = Depends(require_admin)
) -> UserRow:
    """Admin-only endpoint to create a new user account."""
    uid = str(uuid.uuid4())
    con = connect()
    existing = con.execute(
        "SELECT id FROM users WHERE username = ?", [body.username]
    ).fetchone()
    if existing is not None:
        con.close()
        raise HTTPException(status.HTTP_409_CONFLICT, "username taken")
    con.execute(
        "INSERT INTO users (id, username, password_hash, is_admin) VALUES (?, ?, ?, ?)",
        [uid, body.username, hash_password(body.password), body.is_admin],
    )
    con.close()
    return UserRow(id=uid, username=body.username, is_admin=body.is_admin)
