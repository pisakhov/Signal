"""Admin-managed OpenAI-compatible model configurations."""
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Optional

import litellm
from dotenv import set_key
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import UserRow, current_user, require_admin
from .db import connect
from .settings import ROOT


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])

ENV_FILE = ROOT / ".env"


class ModelConfigOut(BaseModel):
    """Public view of a model config (api_key_env hidden)."""

    id: str
    label: str
    model: str
    base_url: str
    created_at: datetime


class CreateModelIn(BaseModel):
    """Admin payload for registering a new model."""

    label: str
    model: str
    base_url: str
    api_key_env: str
    api_key: Optional[str] = None


class UpdateModelIn(BaseModel):
    """Admin payload for editing an existing model."""

    label: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    api_key: Optional[str] = None


def _row_to_out(row) -> ModelConfigOut:
    return ModelConfigOut(
        id=row[0], label=row[1], model=row[2], base_url=row[3], created_at=row[4]
    )


@router.get("", response_model=list[ModelConfigOut])
def list_models(_: UserRow = Depends(current_user)) -> list[ModelConfigOut]:
    """Return every model config available for chat selection."""
    con = connect()
    rows = con.execute(
        "SELECT id, label, model, base_url, created_at FROM model_configs ORDER BY created_at"
    ).fetchall()
    con.close()
    return [_row_to_out(r) for r in rows]


@router.post("", response_model=ModelConfigOut)
def create_model(
    body: CreateModelIn, _: UserRow = Depends(require_admin)
) -> ModelConfigOut:
    """Admin-only: register a model and persist its API key in `.env`."""
    mid = str(uuid.uuid4())
    con = connect()
    existing = con.execute(
        "SELECT id FROM model_configs WHERE label = ?", [body.label]
    ).fetchone()
    if existing is not None:
        con.close()
        raise HTTPException(status.HTTP_409_CONFLICT, "label taken")
    con.execute(
        "INSERT INTO model_configs (id, label, model, base_url, api_key_env) VALUES (?, ?, ?, ?, ?)",
        [mid, body.label, body.model, body.base_url, body.api_key_env],
    )
    row = con.execute(
        "SELECT id, label, model, base_url, created_at FROM model_configs WHERE id = ?",
        [mid],
    ).fetchone()
    con.close()
    if body.api_key:
        ENV_FILE.touch(exist_ok=True)
        set_key(str(ENV_FILE), body.api_key_env, body.api_key, quote_mode="never")
        os.environ[body.api_key_env] = body.api_key
    return _row_to_out(row)


@router.patch("/{model_id}", response_model=ModelConfigOut)
def update_model(
    model_id: str, body: UpdateModelIn, _: UserRow = Depends(require_admin)
) -> ModelConfigOut:
    """Admin-only: edit a model config; optionally rewrite its API key in `.env`."""
    con = connect()
    current = con.execute(
        "SELECT id, label, model, base_url, api_key_env FROM model_configs WHERE id = ?",
        [model_id],
    ).fetchone()
    if current is None:
        con.close()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model not found")
    label = body.label if body.label is not None else current[1]
    model = body.model if body.model is not None else current[2]
    base_url = body.base_url if body.base_url is not None else current[3]
    api_key_env = body.api_key_env if body.api_key_env is not None else current[4]
    if body.label is not None and body.label != current[1]:
        clash = con.execute(
            "SELECT id FROM model_configs WHERE label = ? AND id <> ?",
            [body.label, model_id],
        ).fetchone()
        if clash is not None:
            con.close()
            raise HTTPException(status.HTTP_409_CONFLICT, "label taken")
    con.execute(
        "UPDATE model_configs SET label = ?, model = ?, base_url = ?, api_key_env = ? WHERE id = ?",
        [label, model, base_url, api_key_env, model_id],
    )
    row = con.execute(
        "SELECT id, label, model, base_url, created_at FROM model_configs WHERE id = ?",
        [model_id],
    ).fetchone()
    con.close()
    if body.api_key:
        ENV_FILE.touch(exist_ok=True)
        set_key(str(ENV_FILE), api_key_env, body.api_key, quote_mode="never")
        os.environ[api_key_env] = body.api_key
    return _row_to_out(row)


@router.delete("/{model_id}")
def delete_model(model_id: str, _: UserRow = Depends(require_admin)) -> dict:
    """Admin-only: remove a model config."""
    con = connect()
    con.execute("DELETE FROM model_configs WHERE id = ?", [model_id])
    con.close()
    return {"status": "ok"}


class TestModelOut(BaseModel):
    """Result of a live ping against a model config."""

    ok: bool
    message: str
    latency_ms: int


@router.post("/{model_id}/test", response_model=TestModelOut)
def test_model(
    model_id: str, _: UserRow = Depends(require_admin)
) -> TestModelOut:
    """Send a 1-token ping to the configured model and report the outcome."""
    model_name, base_url, api_key = resolve(model_id)
    logger.info(
        "model.test start id=%s model=%s base_url=%s key_len=%d",
        model_id,
        model_name,
        base_url,
        len(api_key),
    )
    t0 = time.perf_counter()
    try:
        response = litellm.completion(
            model=f"openai/{model_name}",
            api_base=base_url,
            api_key=api_key,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        reply = response.choices[0].message.content or ""
        logger.info(
            "model.test ok id=%s latency_ms=%d reply=%r",
            model_id,
            latency_ms,
            reply[:80],
        )
        return TestModelOut(
            ok=True, message=f"OK ({latency_ms} ms)", latency_ms=latency_ms
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        logger.exception(
            "model.test fail id=%s latency_ms=%d", model_id, latency_ms
        )
        return TestModelOut(
            ok=False, message=f"{type(exc).__name__}: {exc}", latency_ms=latency_ms
        )


def resolve(model_id: str):
    """Return (model, base_url, api_key) for a stored config, or raise 404."""
    con = connect()
    row = con.execute(
        "SELECT model, base_url, api_key_env FROM model_configs WHERE id = ?",
        [model_id],
    ).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model not found")
    api_key = os.environ.get(row[2], "")
    if not api_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"missing env var {row[2]}")
    return row[0], row[1], api_key
