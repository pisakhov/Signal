# Signal
Local workspace for sandboxed Dash-app research projects with an in-browser chat agent (Google ADK).
Each project is a self-contained folder with its own `dash_app.py`, spawned as a subprocess on a dedicated port.

> **Note**: This is a public repo intended for local, single-user use. See the Security section below before running it anywhere else.

## Stack
- **Frontend**: Next.js 16 (App Router, TypeScript) via Bun, Tailwind CSS v4, shadcn/ui, lucide-react, Monaco.
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
- API keys for LiteLLM-compatible providers (OpenAI, Anthropic, etc.)

## Install
```bash
git clone https://github.com/pisakhov/Signal.git
cd Signal

# Env file — fill in ADMIN_PASSWORD and generate SESSION_SECRET
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

## Production Deployment

For production deployment, consider:

1. **Use a process manager** like `gunicorn` with `uvicorn` workers:
   ```bash
   gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

2. **Set environment variables**:
   - `SESSION_SECRET`: Must be a secure random value
   - `CORS_ORIGINS`: Set to your frontend domain
   - `DASH_BASE_URL`: Set to your public URL for Dash iframe access

3. **Use HTTPS**: Configure a reverse proxy (nginx) with SSL certificates

4. **Enable rate limiting**: Configure rate limits in `middleware.py`

5. **Database**: Consider using PostgreSQL instead of DuckDB for multi-user deployments

See [SPECS.md](SPECS.md) for detailed architecture documentation.

## Conventions
- Python is always invoked via `uv run python3 ...` inside `apps/api`.
- The agent's bash tool only accepts a small whitelist (see `apps/api/app/utils.py`).
- `templates/dash_app.py` is protected — the agent cannot overwrite it.
- New projects are created under `./projects/<slug>/` and served on ports starting at `DASH_PORT_RANGE_START`.

## Security
- **Never commit `.env`.** Treat any key that has touched it as potentially leaked — rotate keys.
- `SESSION_SECRET` must be a real random value; the app will reject insecure values.
- The agent `bash` tool runs argv-style (no shell) and rejects shell metacharacters, but it is **not** a security boundary — the whitelist still allows running arbitrary Python in the project sandbox.
- Dash subprocesses are isolated with a whitelisted environment (no parent secrets) and bound to `127.0.0.1`.
- The `/dashboard/[id]` route is restricted to published projects.
- Security headers (CSP, X-Frame-Options, etc.) are enforced via middleware.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to Signal.

## License
MIT — see [LICENSE](LICENSE) for details.
