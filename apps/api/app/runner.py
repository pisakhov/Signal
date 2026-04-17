"""Spawn and manage per-project Dash subprocesses."""
import os
import socket
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional

from .settings import settings


_processes: Dict[str, subprocess.Popen] = {}
_logs: Dict[str, Deque[str]] = {}


def _find_free_port(start: int) -> int:
    """Return the first available TCP port at or after `start`."""
    port = start
    while port < start + 1000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("no free port")


def _wait_for_port(port: int, proc: subprocess.Popen, timeout: float = 8.0) -> None:
    """Block until the child is accepting TCP on `port`, or the child dies."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return
        except OSError:
            time.sleep(0.15)


def _drain(slug: str, proc: subprocess.Popen) -> None:
    """Forward each line of subprocess output into the slug's log buffer."""
    buf = _logs[slug]
    assert proc.stdout is not None
    for line in proc.stdout:
        buf.append(line)
    buf.append(f"[process exited with code {proc.wait()}]\n")


def status(slug: str) -> Optional[int]:
    """Return the port if a process is alive for this project, else None."""
    proc = _processes.get(slug)
    if proc is None or proc.poll() is not None:
        return None
    return getattr(proc, "_port", None)


def logs(slug: str) -> str:
    """Return the captured stdout+stderr text for the project's latest run."""
    return "".join(_logs.get(slug, []))


def stop(slug: str) -> None:
    """Terminate the running process for this project, if any."""
    proc = _processes.pop(slug, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def start(slug: str, preferred_port: Optional[int] = None) -> int:
    """Restart the project's Dash app, returning the bound port."""
    stop(slug)
    cwd = Path(settings.projects_root).resolve() / slug
    entry = cwd / "dash_app.py"
    if not entry.is_file():
        raise FileNotFoundError(str(entry))
    port = _find_free_port(preferred_port or settings.dash_port_range_start)
    env = {**os.environ, "PORT": str(port), "HOST": "127.0.0.1", "PYTHONUNBUFFERED": "1"}
    _logs[slug] = deque(maxlen=1000)
    api_project = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen(
        ["uv", "run", "--project", str(api_project), "python3", "-u", str(entry)],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    proc._port = port  # type: ignore[attr-defined]
    _processes[slug] = proc
    threading.Thread(target=_drain, args=(slug, proc), daemon=True).start()
    _wait_for_port(port, proc)
    return port
