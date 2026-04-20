# Contributing to Signal

Thank you for your interest in contributing to Signal! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- [Bun](https://bun.sh) ≥ 1.1
- [uv](https://docs.astral.sh/uv/) ≥ 0.4
- Python 3.11+
- A code editor (VS Code recommended)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/Signal.git
cd Signal

# Generate secure SESSION_SECRET
printf "SESSION_SECRET=%s\n" "$(openssl rand -hex 32)" >> .env

# Backend setup
cd apps/api
uv sync

# Frontend setup
cd ../web
bun install
```

### Running Development Servers

```bash
# Terminal 1: Backend
cd apps/api
uv run uvicorn app.main:app --port 8000 --reload

# Terminal 2: Frontend
cd apps/web
bun dev
```

Visit http://localhost:3000 to access the application.

## Code Conventions

### Python (Backend)

- Use `uv run python3 ...` to run Python scripts
- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Keep functions focused and under 50 lines when possible
- Use Pydantic models for all API request/response types

### TypeScript (Frontend)

- Use TypeScript strict mode
- Prefer functional components with hooks
- Use shadcn/ui components when available
- Keep components focused and reusable
- Use the `cn()` utility for className merging

### File Naming

- Python: `snake_case.py`
- TypeScript: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- Directories: `kebab-case/`

## Project Structure

```
apps/
├── api/                    # FastAPI backend
│   └── app/
│       ├── agent/          # Google ADK agent system
│       ├── main.py         # FastAPI app entry point
│       ├── auth.py         # Authentication logic
│       ├── chat.py         # SSE chat endpoint
│       ├── projects.py     # Project CRUD operations
│       ├── files.py        # Filesystem helpers
│       ├── runner.py       # Dash subprocess manager
│       ├── db.py           # DuckDB connection
│       ├── settings.py     # Configuration
│       ├── utils.py        # Shared utilities
│       └── middleware.py   # Security middleware
└── web/                    # Next.js frontend
    ├── app/                # Next.js App Router pages
    ├── components/         # React components
    │   ├── ui/            # shadcn/ui base components
    │   ├── chat/          # Chat panel
    │   ├── editor/        # Code editor
    │   ├── files/         # File browser
    │   ├── dash/          # Dash iframe
    │   ├── history/       # Version history
    │   ├── gallery/       # Project gallery
    │   └── admin/         # Admin dialogs
    └── lib/               # Utilities and API client
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

- Write clear, concise commit messages
- Follow the existing code style
- Add tests for new functionality (if applicable)
- Update documentation as needed

### 3. Test Your Changes

- Test both frontend and backend changes
- Verify the agent system works with your changes
- Check for console errors and warnings
- Test with both owned and published projects

### 4. Submit a Pull Request

- Push your branch to GitHub
- Create a pull request with a clear description
- Link related issues if applicable
- Request review from maintainers

## Pull Request Guidelines

### Title Format

- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Examples:
  - `feat: add file upload functionality`
  - `fix: resolve race condition in agent tools`
  - `docs: update README with new features`

### Description

Include:
- What changes were made and why
- How to test the changes
- Any breaking changes or migration notes
- Screenshots for UI changes (if applicable)

## Testing

### Backend Tests

```bash
cd apps/api
uv run pytest  # When tests are added
```

### Manual Testing Checklist

- [ ] User can login and logout
- [ ] Projects can be created, edited, deleted
- [ ] Agent can read, write, and edit files
- [ ] Agent can run bash commands
- [ ] Dash apps start and stop correctly
- [ ] Version history and revert work
- [ ] Published projects can be viewed by others
- [ ] Forking works correctly

## Security Considerations

- Never commit `.env` files or API keys
- Validate all user inputs
- Use parameterized queries to prevent injection
- Keep dependencies up to date
- Follow security best practices in the [SPECS.md](SPECS.md)

## Questions or Issues?

- Open an issue on GitHub for bugs or feature requests
- Start a discussion for questions or design proposals
- Check existing issues before creating new ones

## License

By contributing to Signal, you agree that your contributions will be licensed under the MIT License.
