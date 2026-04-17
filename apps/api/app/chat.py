"""Agent chat endpoint streaming ADK events via SSE."""
import json
import logging
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import routers_models
from .agent.agent import build_agent
from .auth import UserRow, current_user
from .db import connect
from .settings import settings


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["chat"])


class ChatIn(BaseModel):
    """User prompt payload."""

    message: str
    model_id: str


_SELECT = (
    "SELECT p.id, p.owner_id, p.slug FROM projects p WHERE p.id = ?"
)


def _project_root_for(project_id: str, user: UserRow) -> tuple[Path, str]:
    con = connect()
    row = con.execute(_SELECT, [project_id]).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if row[1] != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your project")
    return Path(settings.projects_root).resolve() / row[2], row[2]


@router.post("/{project_id}/chat")
async def chat(
    project_id: str, body: ChatIn, user: UserRow = Depends(current_user)
):
    """Stream ADK agent events as Server-Sent Events."""
    project_root, slug = _project_root_for(project_id, user)
    model_name, base_url, api_key = routers_models.resolve(body.model_id)
    model = LiteLlm(
        model=f"openai/{model_name}", api_base=base_url, api_key=api_key
    )
    agent = build_agent(project_root, slug, model=model)
    runner = InMemoryRunner(agent=agent, app_name="quant-research")
    session = await runner.session_service.create_session(
        app_name="quant-research", user_id=user.id
    )
    content = types.Content(role="user", parts=[types.Part(text=body.message)])

    async def stream() -> AsyncIterator[dict]:
        logger.info("chat.stream start project=%s model=%s", project_id, model_name)
        event_count = 0
        try:
            async for event in runner.run_async(
                user_id=user.id, session_id=session.id, new_message=content
            ):
                event_count += 1
                payload = {"author": event.author, "partial": bool(event.partial)}
                part_kinds = []
                if event.content and event.content.parts:
                    for p in event.content.parts:
                        if p.text:
                            part_kinds.append("text")
                        elif getattr(p, "function_call", None):
                            part_kinds.append(f"call:{p.function_call.name}")
                        elif getattr(p, "function_response", None):
                            part_kinds.append(f"resp:{p.function_response.name}")
                        else:
                            part_kinds.append("other")
                    texts = [p.text for p in event.content.parts if p.text]
                    if texts:
                        payload["text"] = "".join(texts)
                logger.info(
                    "chat.event #%d author=%s partial=%s parts=%s text_len=%d",
                    event_count,
                    event.author,
                    event.partial,
                    part_kinds,
                    len(payload.get("text", "")),
                )
                yield {"event": "message", "data": json.dumps(payload)}
        except Exception:
            logger.exception("chat.stream error project=%s", project_id)
            yield {
                "event": "message",
                "data": json.dumps({"author": "system", "text": "stream error"}),
            }
        logger.info("chat.stream done project=%s events=%d", project_id, event_count)
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(stream())
