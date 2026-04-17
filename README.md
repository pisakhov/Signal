# Signal
Local workspace for sandboxed Dash-app research projects with an in-browser chat agent (Google ADK).
Each project is a self-contained folder with its own `dash_app.py`, spawned as a subprocess on a dedicated port.
> Public repo — intended for local, single-user use. See the Security section below before running it anywhere else.
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

# Env file — fill in ADMIN_PASSWORD, GOOGLE_API_KEY, etc.
# Generate a real SESSION_SECRET (the template value is a placeholder):
cp .env.example .env
printf "SESSION_SECRET=%s\n" "$(openssl rand -hex 32)" >> .env

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
## Security
- **Never commit `.env`.** It's gitignored, but treat any key that has touched it as potentially leaked — rotate keys when moving between environments.
- `SESSION_SECRET` must be a real random value (`openssl rand -hex 32`); the `change-me` placeholder would let anyone forge admin JWTs.
- The agent `bash` tool runs argv-style (no shell) and rejects shell metacharacters (`;&|><\`$`), but it is **not** a security boundary — the whitelist (including `uv`) still allows running arbitrary Python in the project sandbox. Do not expose this service to untrusted users.
- Dash subprocesses are started with a whitelisted environment (no parent secrets inherited) and bound to `127.0.0.1`. The `/dashboard/[id]` share route is restricted to published projects.
- Only project owners can redeploy/stop; `/models/{id}/test` is admin-only.
## License
MIT — see `LICENSE` if present; otherwise all code is provided as-is, without warranty.
