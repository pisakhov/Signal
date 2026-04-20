# Signal: Architecture Specification

This document describes how to engineer a Signal-like application from scratch. Signal is a local workspace for sandboxed Dash-app research projects with an in-browser AI coding agent.

## System Overview

Signal is a monorepo containing:
- **Frontend**: Next.js 16 App Router with TypeScript
- **Backend**: FastAPI with Google ADK (Agent Development Kit)
- **Storage**: DuckDB for metadata, filesystem for project sandboxes
- **Runtime**: Each project runs as an isolated Dash subprocess on a dedicated port

## High-Level Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Browser       │      │   FastAPI       │      │  Dash Subprocess│
│   (Next.js)     │◄────►│   Backend       │◄────►│  (per project)  │
│                 │      │                 │      │                 │
│  - Gallery      │      │  - Auth (JWT)   │      │  - Port 8100+   │
│  - Project View │      │  - Projects API │      │  - Isolated env │
│  - Chat Panel   │      │  - Chat (SSE)   │      │  - Auto-restart │
│  - File Editor  │      │  - Models       │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                 │
                                 ▼
                         ┌─────────────────┐
                         │  DuckDB + Files │
                         │  - Metadata     │
                         │  - Project dirs │
                         └─────────────────┘
```

## Part 1: Backend (FastAPI)

### 1.1 Project Structure

```
apps/api/
├── app/
│   ├── main.py              # FastAPI app with CORS, middleware & router wiring
│   ├── settings.py          # Pydantic settings from .env
│   ├── db.py                # DuckDB connection & schema
│   ├── auth.py              # JWT + bcrypt auth primitives
│   ├── runner.py            # Dash subprocess manager
│   ├── chat.py              # SSE streaming for ADK agent
│   ├── projects.py          # Project CRUD + file operations
│   ├── files.py             # Sandboxed filesystem helpers
│   ├── utils.py             # Shared utilities (git, constants)
│   ├── middleware.py        # Security middleware (rate limit, headers, logging)
│   ├── routers_auth.py      # Auth endpoints (login, register)
│   └── routers_models.py    # Model configuration endpoints
│   └── agent/
│       ├── agent.py         # Google ADK agent builder
│       └── tools.py         # Sandboxed tools (read, write, edit, bash)
├── scripts/
│   └── test_chat.py         # End-to-end test script
├── pyproject.toml           # Python dependencies (uv)
└── .python-version          # Python 3.11+
```

### 1.2 Database Schema (DuckDB)

```sql
-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Projects table
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    port INTEGER,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    current_commit TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Model configurations table
CREATE TABLE model_configs (
    id TEXT PRIMARY KEY,
    label TEXT UNIQUE NOT NULL,
    model TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key_env TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 1.3 Authentication

**JWT-based authentication with bcrypt password hashing:**

```python
# Key functions in auth.py:
- hash_password(plain: str) -> str
- verify_password(plain: str, hashed: str) -> bool
- create_token(user_id: str) -> str  # JWT with 7-day expiry
- current_user(request) -> UserRow    # FastAPI dependency
- require_admin(user) -> UserRow      # Admin-only dependency
- authenticate(username, password) -> UserRow | None
```

**JWT payload:**
```json
{
  "sub": "user_id",
  "exp": "timestamp"  // 7 days from issuance
}
```

**Environment variables:**
- `SESSION_SECRET`: JWT signing key (MUST be secure random)
- `ADMIN_USERNAME`: Initial admin username
- `ADMIN_PASSWORD`: Initial admin password (auto-seeded on first boot)

**SESSION_SECRET validation:**
The application validates that `SESSION_SECRET` is not set to common insecure values like `"change-me"`, `"changeme"`, or empty string. The app will exit with an error if an insecure value is detected.

### 1.4 Security Middleware

**Rate Limiting:**
- In-memory rate limiting by user ID or IP address (active on all routes)
- Configurable requests per minute (default: 60) and burst allowance (default: 10)
- Skipped for health check endpoint
- Returns HTTP 429 when limit exceeded

**Security Headers:**
- Content-Security-Policy (CSP): Restricts sources for scripts, styles, frames
- X-Content-Type-Options: Prevents MIME sniffing
- X-Frame-Options: set to `SAMEORIGIN` to allow iframe embedding of Dash apps
- X-XSS-Protection: Enables browser XSS filter
- Referrer-Policy: Controls referrer information
- Permissions-Policy: Restricts browser features
- Strict-Transport-Security (HSTS): Enforces HTTPS in production

**Request Logging:**
- Logs all requests with method, path, and client IP
- Logs responses with status code and duration
- Adds `X-Response-Time` header
- Logs errors with stack traces

**File Size Limits:**
- Maximum file size: 10 MB per file
- Returns HTTP 413 if exceeded

**Orphaned Process Cleanup:**
- On startup, stops any tracked Dash processes from previous runs
- Prevents port conflicts and zombie processes

### 1.5 Shared Utilities

**File: `apps/api/app/utils.py`**

Contains shared constants and functions used across multiple modules:

```python
# Protected files that cannot be deleted or renamed
PROTECTED_FILES = {"dash_app.py", ".git", ".gitignore"}

# Bash command whitelist for owners
BASH_WHITELIST = {
    "ls", "pwd", "cat", "head", "tail", "grep", "rg", "find", "tree",
    "wc", "which", "echo", "touch", "mkdir", "mv", "cp", "rm",
    "redeploy", "uv", "git"
}

# Read-only bash whitelist for non-owners
READONLY_BASH_WHITELIST = {
    "ls", "pwd", "cat", "head", "tail", "grep", "rg", "find", "tree",
    "wc", "which", "echo"
}

# Git functions
init_git_repo(project_path, commit_message="Initial commit") -> Optional[str]
git_commit(project_path, message, author_name, author_email) -> Optional[str]
get_current_commit(project_path) -> Optional[str]
ensure_git_repo(project_path) -> bool
```

### 1.6 Project Management

**Project lifecycle:**

1. **Create** (`POST /projects`):
   - Generate unique slug: `{title}-{random-6-hex}`
   - Create directory under `projects_root/{slug}/`
   - Copy `templates/dash_app.py` as entry point
   - Initialize git repo with initial commit
   - Insert row into database

2. **Read** (`GET /projects`, `GET /projects/{id}`):
   - List: returns user's projects + all published projects
   - Single: requires ownership OR published status

3. **Update**:
   - `PUT /projects/{id}/file`: Write file content (auto-commits to git)
   - `POST /projects/{id}/file/rename`: Rename file (auto-commits)
   - `DELETE /projects/{id}/file`: Delete file (auto-commits)
   - `POST /projects/{id}/publish`: Toggle published flag

4. **Delete** (`DELETE /projects/{id}`):
   - Stop Dash subprocess
   - Delete project directory
   - Remove database row

5. **Fork** (`POST /projects/{id}/fork`):
   - Copy entire project directory
   - Initialize fresh git history
   - Create new database row owned by forker
   - "copy" suffix for own projects, "fork" for others

### 1.7 File Operations (Sandboxed)

**Security constraints:**
- All paths resolved relative to project root
- Path traversal rejected (`../`, absolute paths)
- Protected files: `dash_app.py` cannot be deleted/renamed
- Git auto-commit on all write operations

**Functions in `files.py`:**
```python
- resolve(slug, rel) -> Path      # Safe path resolution
- list_tree(slug) -> List[dict]   # Recursive file listing
- read_text(slug, rel) -> str     # Read file content
- write_text(slug, rel, content)  # Write file
- delete(slug, rel)               # Delete file
- rename(slug, from, to)          # Rename file
```

### 1.8 Dash Subprocess Manager

**Port allocation:**
- Start at `DASH_PORT_RANGE_START` (default 8100)
- Find first available port in range
- Reuse previous port if available

**Process lifecycle:**
```python
def start(slug: str, preferred_port: int | None) -> int:
    1. Stop existing process if running
    2. Find entry point: projects/{slug}/dash_app.py
    3. Allocate port
    4. Spawn: uv run --project {api_project} python3 -u dash_app.py
    5. Whitelist env: PATH, HOME, PORT, HOST, PYTHONUNBUFFERED
    6. Capture stdout/stderr in rotating buffer (max 1000 lines)
    7. Wait for port to be listening (8s timeout)
    8. Return port
```

**Process isolation:**
- Bound to `127.0.0.1` only
- No parent environment variables (no secrets leaked)
- Separate `uv run` context per project

### 1.9 Git Integration

**Auto-commit triggers:**
- File write via API
- File edit via agent
- File rename/delete via agent
- Bash commands: `rm`, `mv`, `cp`, `touch`, `mkdir`

**Commit metadata:**
- Author: "Signal <signal@local>" or "Agent <agent@signal.local>"
- Message format: `"Edit {path}"`, `"Agent: edit {path}"`, etc.
- Stored in `projects.current_commit` column

**History features:**
- `GET /projects/{id}/history`: List git commits
- `POST /projects/{id}/revert`: Checkout specific commit

### 1.10 Agent System (Google ADK)

**Agent builder:**
```python
def build_agent(project_root: Path, slug: str, model: LiteLlm) -> Agent:
    return Agent(
        name="project_assistant",
        model=model,
        description="Assistant for sandboxed Dash research project.",
        instruction=INSTRUCTION,  # Detailed system prompt
        tools=make_tools(project_root, slug),
    )
```

**Tools available to agent:**
1. `read_file(path: str) -> Dict`: Read file content
2. `write_file(path: str, content: str) -> Dict`: Create/overwrite file
3. `edit_file(path: str, search: str, replace: str) -> Dict`: Replace first occurrence
4. `bash(command: str) -> Dict`: Run whitelisted shell command

**Bash whitelist:**
```python
BASH_WHITELIST = {
    "ls", "pwd", "cat", "head", "tail", "grep", "rg", "find", "tree",
    "wc", "which", "echo", "touch", "mkdir", "mv", "cp", "rm",
    "redeploy", "uv", "git"
}
```

**Bash security:**
- Argv-style execution (no shell)
- Rejects metacharacters: `;&|><`$\n\r`
- Protected files: `dash_app.py`, `.git`, `.gitignore`

**Redeploy command:**
- Special bash command that restarts Dash subprocess
- Updates database with new port and commit hash
- Waits 1.5s for startup
- Returns error if crash detected

**Read-only mode (for published projects):**
- `build_readonly_agent()` with restricted tools
- No write/edit/bash commands
- Only `read_file` and safe bash (`ls`, `cat`, `grep`, etc.)

### 1.11 Chat Endpoint (SSE)

**Endpoint:** `POST /projects/{id}/chat`

**Flow:**
1. Resolve project root and verify access (owner OR published)
2. Resolve model configuration (LiteLLM-compatible)
3. Build appropriate agent (full or read-only)
4. Create ADK InMemoryRunner session
5. Stream events as Server-Sent Events

**Event format:**
```
event: message
data: {"author": "user", "text": "...", "partial": false}

event: message
data: {"author": "model", "text": "...", "partial": true}

event: done
data: {}
```

**Model resolution:**
- Reads from `model_configs` table
- Constructs LiteLLM model: `openai/{model_name}`
- API key from environment variable

### 1.12 Model Management

**Admin-only endpoints:**
- `GET /models`: List all model configs
- `POST /models`: Create new config (writes API key to .env)
- `PATCH /models/{id}`: Update config
- `DELETE /models/{id}`: Delete config
- `POST /models/{id}/test`: Ping model with 1-token request

**Model config schema:**
```python
{
  "id": "uuid",
  "label": "Display name",
  "model": "gpt-4o",           # LiteLLM model name
  "base_url": "https://...",   # OpenAI-compatible endpoint
  "api_key_env": "OPENAI_API_KEY",  # Env var name
  "created_at": "timestamp"
}
```

**API key storage:**
- Keys written to `.env` file using `python-dotenv`
- Never returned in API responses
- Loaded at runtime from environment

## Part 2: Frontend (Next.js)

### 2.1 Project Structure

```
apps/web/
├── app/
│   ├── layout.tsx             # Root layout with fonts
│   ├── page.tsx               # Gallery (project list)
│   ├── login/
│   │   └── page.tsx           # Login page
│   ├── project/
│   │   └── [id]/
│   │       └── page.tsx       # Project editor with chat + files
│   └── dashboard/
│       └── [id]/
│           └── page.tsx       # Fullscreen iframe for published projects
├── components/
│   ├── ui/                    # shadcn/ui base components
│   ├── gallery/               # Gallery components
│   ├── chat/                  # Chat panel
│   ├── editor/                # Monaco editor
│   ├── files/                 # File browser
│   ├── dash/                  # Dash iframe
│   ├── history/               # Version history
│   └── admin/                 # Admin dialogs
├── lib/
│   ├── api.ts                 # Typed API client
│   ├── auth.ts                # JWT token management
│   └── utils.ts               # Utilities (cn, languageFor)
├── package.json
├── tsconfig.json
├── next.config.ts
└── tailwind.config.js
```

### 2.2 API Client

**Typed fetch wrapper:**
```typescript
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return await res.json();
}
```

**API methods:**
- `login(username, password)`: Authenticate and get token
- `me()`: Get current user
- `listProjects()`: Get accessible projects
- `createProject(title)`: Create new project
- `deleteProject(id)`: Delete project
- `publish(id)`: Toggle published flag
- `listFiles(id)`: List project files
- `readFile(id, path)`: Read file content
- `writeFile(id, path, content)`: Write file
- `deleteFile(id, path)`: Delete file
- `renameFile(id, from, to)`: Rename file
- `redeploy(id)`: Restart Dash subprocess
- `start(id)`: Start published project
- `stop(id)`: Stop Dash subprocess
- `logs(id)`: Get subprocess logs
- `history(id)`: Get git history
- `revert(id, commit)`: Revert to commit
- `fork(id)`: Fork/duplicate project
- `listModels()`: Get model configs
- `createModel(...)`: Create model config (admin)
- `updateModel(id, ...)`: Update model (admin)
- `deleteModel(id)`: Delete model (admin)
- `testModel(id)`: Test model connection (admin)
- `chatUrl(id)`: Get SSE endpoint for chat

### 2.3 Authentication

**Token storage:**
```typescript
// lib/auth.ts
const TOKEN_KEY = "signal_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
```

### 2.4 Pages

**Gallery (`app/page.tsx`):**
- Lists user's projects + all published projects
- Admin sees "Models" and "New user" buttons
- Create, delete, publish, fork projects
- Logout button

**Login (`app/login/page.tsx`):**
- Username/password form
- Stores JWT token on success
- Redirects to gallery

**Project Editor (`app/project/[id]/page.tsx`):**
- Left sidebar: Chat panel
- Right tabs: Files / App
- Files tab: File browser + Monaco editor
- App tab: Dash iframe
- Fork/Duplicate button for copying

**Fullscreen Dashboard (`app/dashboard/[id]/page.tsx`):**
- Read-only view of published projects
- Fullscreen Dash iframe
- No chat or file editing

### 2.5 Components

**ChatPanel:**
- SSE connection to `/projects/{id}/chat`
- Model selection dropdown
- Message history with user/agent bubbles
- Auto-scroll to latest message
- Calls `onAgentDone` after completion (triggers file refresh)

**FilesPane:**
- File tree view
- Click to open in Monaco editor
- Create, delete, rename files (owner only)
- Shows file sizes

**MonacoEditor:**
- Full code editor with syntax highlighting
- Save button (Cmd+S)
- Auto-saves on blur

**DashIframe:**
- Iframe pointing to `http://localhost:{port}`
- Refresh button
- Shows "Waiting for port..." while starting
- Displays logs if crash detected

**VersionHistory:**
- Git commit list
- Revert button per commit
- Shows hash, message, author, timestamp

**ProjectCard:**
- Title, owner, updated timestamp
- Published badge
- Fork button (published projects)
- Delete button (own projects)
- Publish toggle (own projects)

### 2.6 UI Framework

**shadcn/ui + Tailwind CSS v4**
- Components in `components/ui/`
- Dark mode support via `next-themes`
- Toast notifications via `sonner`
- Icons via `lucide-react`

**Tailwind config:**
- CSS variables for theming
- Custom animations via `tw-animate-css`

## Part 3: Environment Variables

### 3.1 Backend (.env)

```bash
# Admin user (auto-seeded on first boot)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# Database
DUCKDB_PATH=./data/metadata.duckdb

# Project storage
PROJECTS_ROOT=./projects
TEMPLATE_DASH=./templates/dash_app.py
DASH_PORT_RANGE_START=8100

# Server
API_PORT=8000

# Security (CRITICAL: generate with openssl rand -hex 32)
SESSION_SECRET=your-random-32-byte-hex-string

# CORS (comma-separated list of allowed origins)
CORS_ORIGINS=http://localhost:3000

# Optional: Model API keys (added via admin UI)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
```

### 3.2 Frontend (.env.local)

```bash
# API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional: Base URL for Dash apps (for remote deployment)
# Leave empty for local development
NEXT_PUBLIC_DASH_BASE_URL=
```

## Part 4: Deployment Considerations

### 4.1 Security Notes

1. **SESSION_SECRET**: MUST be random 32-byte hex. The app validates and rejects empty or common insecure values like `"change-me"`, `"changeme"`, `"secret"`, `"password"`.
2. **Never commit .env**: Rotate any keys that touched a committed .env file.
3. **Bash tool is NOT a security boundary**: The whitelist allows arbitrary Python via `uv run`.
4. **Dash subprocesses**: Bound to 127.0.0.1 with isolated environment.
5. **CORS**: Configurable via `CORS_ORIGINS` environment variable (comma-separated).
6. **/dashboard/{id}**: Restricted to published projects only.
7. **Rate limiting**: Active on all routes (60 req/min, 10 burst) per user/IP.
8. **Security headers**: CSP, X-Frame-Options, HSTS, and others enforced via middleware.
9. **File size limits**: Maximum 10 MB per file write.
10. **Process cleanup**: Orphaned Dash processes are stopped on server startup.

### 4.2 Port Requirements

- Frontend: 3000 (Next.js dev)
- Backend: 8000 (FastAPI)
- Dash apps: 8100+ (dynamic allocation)

### 4.3 Remote Deployment

For remote deployments where the frontend and Dash apps are not on localhost:

1. Set `CORS_ORIGINS` to your frontend domain(s)
2. Set `NEXT_PUBLIC_DASH_BASE_URL` in the frontend to your public URL
3. Configure a reverse proxy (nginx) to handle SSL termination
4. Update CSP headers in middleware to allow your domain
5. Consider using Redis for rate limiting in multi-server deployments

### 4.4 Runtime Dependencies

**Backend:**
- Python 3.11+
- uv (Python package manager)
- All dependencies in `pyproject.toml`

**Frontend:**
- Bun (JavaScript runtime)
- All dependencies in `package.json`

## Part 5: Development Workflow

### 5.1 Initial Setup

```bash
# Clone repo
git clone <repo>
cd <repo>

# Generate secure SESSION_SECRET
printf "SESSION_SECRET=%s\n" "$(openssl rand -hex 32)" >> .env

# Backend
cd apps/api
uv sync

# Frontend
cd apps/web
bun install
```

### 5.2 Running Dev Servers

```bash
# Terminal 1: Backend
cd apps/api
uv run uvicorn app.main:app --port 8000 --reload

# Terminal 2: Frontend
cd apps/web
bun dev
```

### 5.3 Adding New Features

**Backend:**
1. Add endpoint in appropriate router file
2. Add Pydantic models for request/response
3. Update `lib/api.ts` on frontend
4. Handle authentication via `current_user` dependency

**Frontend:**
1. Add page in `app/` or component in `components/`
2. Use `api` client from `lib/api.ts`
3. Handle errors with toast notifications
4. Update auth state on 401 responses

## Part 6: Testing

### 6.1 Key Test Scenarios

1. **Authentication**: Login, logout, token expiry
2. **Project CRUD**: Create, read, update, delete projects
3. **File operations**: Read, write, delete, rename files
4. **Agent chat**: Send prompts, receive responses, tool execution
5. **Dash deployment**: Start, stop, redeploy projects
6. **Forking**: Copy own projects, fork others' projects
7. **Version control**: History view, revert to commit
8. **Model management**: Add, test, remove model configs

### 6.2 Manual Testing Checklist

- [ ] Admin can create users
- [ ] Users can login/logout
- [ ] Projects can be created with dash_app.py template
- [ ] Dash app starts on allocated port
- [ ] Agent can read/write/edit files
- [ ] Agent can run whitelisted bash commands
- [ ] Agent auto-redeploys after code changes
- [ ] Git commits are created on file changes
- [ ] Projects can be published/unpublished
- [ ] Published projects can be viewed by others
- [ ] Published projects use read-only agent
- [ ] Fork creates copy with fresh git history
- [ ] Model configs can be added and tested
- [ ] CORS allows frontend communication

## Part 7: Troubleshooting

### 7.1 Common Issues

**Dash subprocess fails to start:**
- Check logs via `/projects/{id}/logs`
- Verify dash_app.py exists and is valid Python
- Check port availability
- Verify `uv` is installed

**Agent not responding:**
- Check model config has valid API key
- Verify base_url is reachable
- Check LiteLLM compatibility
- View server logs for errors

**Git operations failing:**
- Ensure `.git` directory exists in project folder
- Check file permissions
- Verify git is installed

**CORS errors:**
- Update `allow_origins` in `app/main.py`
- Verify `NEXT_PUBLIC_API_URL` in frontend

### 7.2 Debug Mode

Enable FastAPI debug logging:
```bash
uv run uvicorn app.main:app --port 8000 --log-level debug
```

## Part 8: Extension Points

### 8.1 Adding New Agent Tools

Edit `apps/api/app/agent/tools.py`:

```python
def my_new_tool(arg: str) -> Dict:
    """Tool description."""
    # Implement tool logic
    return {"status": "success", "result": ...}

# Add to make_tools() return list
return [read_file, write_file, edit_file, bash, my_new_tool]
```

### 8.2 Adding New API Endpoints

Create new router in `apps/api/app/`:

```python
from fastapi import APIRouter, Depends
from .auth import current_user

router = APIRouter(prefix="/feature", tags=["feature"])

@router.get("")
def list_features(user = Depends(current_user)):
    return {"features": []}
```

Include in `app/main.py`:
```python
from . import my_router
app.include_router(my_router.router)
```

### 8.3 Custom Dash Templates

Edit `templates/dash_app.py` to change the default project template.

## Part 9: Data Model Summary

**User:**
```typescript
{
  id: string;
  username: string;
  is_admin: boolean;
}
```

**Project:**
```typescript
{
  id: string;
  owner_id: string;
  owner_username: string;
  title: string;
  slug: string;
  port: number | null;
  published: boolean;
  created_at: string;  // ISO timestamp
  updated_at: string;  // ISO timestamp
  owned_by_me: boolean;  // Computed
}
```

**ModelConfig:**
```typescript
{
  id: string;
  label: string;
  model: string;
  base_url: string;
  created_at: string;
}
```

**HistoryEntry:**
```typescript
{
  hash: string;
  short_hash: string;
  message: string;
  author: string;
  timestamp: string;
}
```

**FileEntry:**
```typescript
{
  path: string;
  is_dir: boolean;
  size: number;
}
```

## Part 10: Technology Stack Rationale

| Component | Technology | Reason |
|-----------|-----------|--------|
| Frontend framework | Next.js 16 | Latest App Router, React Server Components |
| UI library | shadcn/ui | Copy-paste components, full customization |
| Styling | Tailwind CSS v4 | Latest version with native CSS cascade |
| Backend framework | FastAPI | Async, type-safe, auto OpenAPI docs |
| Python runtime | uv | Fast package manager, project isolation |
| Database | DuckDB | Embedded, SQL, no separate server |
| Auth | JWT + bcrypt | Stateless, secure password hashing |
| Agent framework | Google ADK | Official agent toolkit |
| Model interface | LiteLLM | Provider-agnostic OpenAI-compatible API |
| Dashboard | Dash | Python web apps, Plotly integration |
| Code editor | Monaco | VS Code's editor, excellent TypeScript support |
| HTTP streaming | SSE (Server-Sent Events) | Simple unidirectional streaming |
