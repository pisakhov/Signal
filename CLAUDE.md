# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Signal is a local workspace for sandboxed Dash-app research projects with an in-browser chat agent (Google ADK). Each project is a self-contained folder with its own `dash_app.py`, spawned as a subprocess on a dedicated port.

## Development Commands

```bash
# Backend (FastAPI + ADK) - always use uv
cd apps/api
uv sync                              # Install dependencies
uv run uvicorn app.main:app --port 8000   # Run dev server
uv run python3 -m pytest             # Run tests (if any)

# Frontend (Next.js) - use Bun
cd apps/web
bun install                          # Install dependencies
bun dev                              # Run dev server on :3000
bun run lint                         # Run ESLint
bun run build                        # Production build
```

## Architecture

### Backend (`apps/api/`)

- **Entry point**: `app/main.py` - FastAPI app with CORS, auth, projects, chat, and models routers
- **Agent**: `app/agent/agent.py` builds a Google ADK Agent with tools scoped to a single project sandbox
- **Tools** (`app/agent/tools.py`): `read_file`, `write_file`, `edit_file`, `bash` (whitelisted commands only)
- **Project runner** (`app/runner.py`): Spawns Dash subprocesses on dedicated ports starting at `DASH_PORT_RANGE_START` (8100)
- **Database** (`app/db.py`): DuckDB for users, projects, and model_configs
- **Chat** (`app/chat.py`): SSE streaming endpoint that runs the ADK agent

### Frontend (`apps/web/`)

- **App Router**: Next.js 16 with App Router (note: breaking changes from older versions)
- **Components**: `components/` organized by feature (chat, editor, files, gallery, admin, dash)
- **API layer**: `lib/api.ts` - typed client for all backend endpoints
- **Auth**: JWT-based, token stored in localStorage

### Key Files

- `templates/dash_app.py` - Copied into each new project as the entry point. **Protected** - the agent cannot overwrite it.
- `.env` - Must contain real `SESSION_SECRET` (generate with `openssl rand -hex 32`)

## Conventions

- Python is always invoked via `uv run python3 ...` inside `apps/api`
- Agent bash tool whitelist: `ls`, `pwd`, `cat`, `head`, `tail`, `grep`, `rg`, `find`, `tree`, `wc`, `which`, `echo`, `touch`, `mkdir`, `mv`, `cp`, `rm`, `redeploy`, `uv`
- Protected files (cannot be deleted/renamed by agent): `dash_app.py`
- Projects are created under `./projects/<slug>/` and served on ports starting at `DASH_PORT_RANGE_START`
- **Agent automatically redeplloys**: After any code edit, the agent calls `bash('redeploy')` itself

## Security Notes

- **Never commit `.env`** - rotate keys if they've ever touched it
- `SESSION_SECRET` must be a real random value - the placeholder allows JWT forgery
- Agent `bash` tool runs argv-style (no shell) and rejects shell metacharacters, but is **not a security boundary** - the whitelist still allows arbitrary Python in the sandbox
- Dash subprocesses are isolated with a whitelisted environment (no parent secrets) and bound to `127.0.0.1`
- `/dashboard/[id]` share route is restricted to published projects only
- Only project owners can redeploy/stop; `/models/{id}/test` is admin-only
