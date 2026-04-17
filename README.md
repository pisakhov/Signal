# Signal
Local workspace for sandboxed Dash-app research projects with an in-browser chat agent (Google ADK).
Each project is a self-contained folder with its own `dash_app.py`, spawned as a subprocess on a dedicated port.
## Stack
- **Frontend**: Next.js (App Router, TypeScript) via Bun, Tailwind CSS v4, shadcn/ui, lucide-react, Monaco.
- **Backend**: FastAPI + Google ADK, managed by `uv`.
- **Agent tools**: `read_file`, `write_file`, `edit_file`, `bash` (whitelisted commands only).
- **Storage**: DuckDB for metadata, filesystem sandboxes for project folders.
- **Models**: LiteLLM-compatible providers, configurable at runtime via the Models marketplace.
## Layout
```
apps/web      # Next.js frontend
apps/api      # FastAPI + ADK backend
templates     # Template dash_app.py copied into each new project
projects      # Sandboxed project folders (gitignored)
data          # DuckDB metadata file (gitignored)
```
## Prerequisites
- [Bun](https://bun.sh) ≥ 1.1
- [uv](https://docs.astral.sh/uv/) ≥ 0.4
- Python 3.11+
- A Google API key (for ADK) and optionally keys for any LiteLLM provider you plan to use.
## Install
```bash
git clone git@github.com:pisakhov/Signal.git
cd Signal

# Env file — fill in ADMIN_PASSWORD, SESSION_SECRET, GOOGLE_API_KEY, etc.
cp .env.example .env

# Backend
cd apps/api
uv sync
cd ../..

# Frontend
cd apps/web
bun install
cd ../..
```
## Run
Start the backend and frontend in two terminals:
```bash
# Terminal 1 — API
cd apps/api
uv run uvicorn app.main:app --port 8000

# Terminal 2 — Web
cd apps/web
bun dev
```
Open http://localhost:3000 and sign in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.
## Conventions
- Python is always invoked via `uv run python3 ...` inside `apps/api`.
- The agent's bash tool only accepts a small whitelist (see `apps/api/app/agent/tools.py`).
- `templates/dash_app.py` is protected — the agent cannot overwrite it.
- New projects are created under `./projects/<slug>/` and served on ports starting at `DASH_PORT_RANGE_START`.
## License
Private — all rights reserved.
