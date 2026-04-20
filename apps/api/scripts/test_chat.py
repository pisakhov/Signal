"""End-to-end smoke test for the chat SSE endpoint.

Run with: `uv run python3 -m scripts.test_chat` from `apps/api`.
Requires uvicorn running on localhost:8000 and env vars:
  TEST_USERNAME, TEST_PASSWORD, TEST_PROJECT_ID, TEST_MODEL_ID.
"""
import json
import os
import sys

import httpx


BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
USERNAME = os.environ.get("TEST_USERNAME", "admin")
PASSWORD = os.environ.get("TEST_PASSWORD")
if not PASSWORD:
    sys.exit("TEST_PASSWORD environment variable is required")
PROJECT_ID = os.environ.get("TEST_PROJECT_ID")
MODEL_ID = os.environ.get("TEST_MODEL_ID")
PROMPT = os.environ.get("TEST_PROMPT", "hi")


def login() -> str:
    """Authenticate and return a bearer token."""
    r = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def pick_project(token: str) -> str:
    """Return the first project the user owns."""
    r = httpx.get(
        f"{BASE_URL}/projects",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        sys.exit("no projects found; create one first")
    return items[0]["id"]


def pick_model(token: str) -> str:
    """Return the first configured model."""
    r = httpx.get(
        f"{BASE_URL}/models",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        sys.exit("no models configured; add one first")
    return items[0]["id"]


def stream_chat(token: str, project_id: str, model_id: str, prompt: str) -> None:
    """Stream the chat SSE response and pretty-print each event."""
    url = f"{BASE_URL}/projects/{project_id}/chat"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = {"message": prompt, "model_id": model_id}
    print(f"POST {url}  prompt={prompt!r} model_id={model_id}")
    with httpx.stream(
        "POST", url, headers=headers, json=payload, timeout=60
    ) as r:
        print(f"status={r.status_code}")
        r.raise_for_status()
        raw_buffer = b""
        event_idx = 0
        for chunk in r.iter_bytes():
            raw_buffer += chunk
            while b"\n\n" in raw_buffer or b"\r\n\r\n" in raw_buffer:
                sep = b"\r\n\r\n" if b"\r\n\r\n" in raw_buffer else b"\n\n"
                block, raw_buffer = raw_buffer.split(sep, 1)
                event_idx += 1
                print(f"--- event #{event_idx} (raw bytes) ---")
                print(block.decode("utf-8", errors="replace"))
                data_line = next(
                    (
                        ln
                        for ln in block.splitlines()
                        if ln.startswith(b"data:")
                    ),
                    None,
                )
                if data_line:
                    data = data_line[5:].strip().decode("utf-8")
                    try:
                        parsed = json.loads(data)
                        print(f"parsed: {parsed}")
                    except json.JSONDecodeError:
                        print(f"non-JSON data: {data!r}")
    print("stream closed")


def main() -> None:
    """Run the full login -> chat streaming flow."""
    token = login()
    project_id = PROJECT_ID or pick_project(token)
    model_id = MODEL_ID or pick_model(token)
    stream_chat(token, project_id, model_id, PROMPT)


if __name__ == "__main__":
    main()
