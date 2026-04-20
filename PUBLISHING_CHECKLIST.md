# Publishing Checklist: Risks, Orphans, and Duplicates

This document identifies items that should be reviewed or cleaned up before publishing the repository publicly.

## Critical Security Items (MUST FIX)

### 1. Hardcoded Credentials in Test Script
**File:** `apps/api/scripts/test_chat.py`
**Issue:** Contains default test credentials
```python
PASSWORD = os.environ.get("TEST_PASSWORD", "1Lk232lmg0")
```
**Risk:** Exposes a default password that might work
**Fix:** Remove the default value, require explicit env var

### 2. Default SESSION_SECRET
**File:** `.env.example`, `apps/api/app/settings.py`
**Issue:** Default `SESSION_SECRET=change-me` allows JWT forgery
**Risk:** Anyone can forge admin tokens
**Fix:** Already documented in README, but consider rejecting the default value at startup

### 3. CORS Configuration
**File:** `apps/api/app/main.py`
**Issue:** Hardcoded `allow_origins=["http://localhost:3000"]`
**Risk:** Breaks in production or different dev setups
**Fix:** Make configurable via environment variable

### 4. Hardcoded localhost URLs
**Files:**
- `apps/web/lib/api.ts`: Default `http://localhost:8000`
- `apps/web/components/dash/DashIframe.tsx`: `http://localhost:${port}`
- `apps/web/app/dashboard/[id]/page.tsx`: `http://localhost:${port}`

**Risk:** Breaks when deployed remotely
**Fix:** Make API URL configurable, proxy Dash apps through backend

## Code Quality Issues

### 1. Duplicate Code - Protected Files Constants
**Files:**
- `apps/api/app/agent/tools.py`: `PROTECTED_FILES = {"dash_app.py", ".git", ".gitignore"}`
- `apps/api/app/files.py`: `PROTECTED_FILES = {"dash_app.py"}`

**Issue:** Same concept defined in two places with different values
**Fix:** Define once in a shared location

### 2. Duplicate Code - Git Commit Functions
**Files:**
- `apps/api/app/projects.py`: `_git_commit()`, `_get_current_commit()`
- `apps/api/app/agent/tools.py`: `_git_commit()`, `_get_current_commit()`

**Issue:** Nearly identical functions in two files
**Fix:** Extract to shared utility module

### 3. Duplicate Code - Bash Whitelist
**Files:**
- `apps/api/app/agent/tools.py`: `BASH_WHITELIST`
- `apps/api/app/agent/tools.py`: `READONLY_BASH_WHITELIST`

**Issue:** Read-only whitelist is a subset, manually maintained
**Fix:** Derive readonly from full whitelist automatically

### 4. Duplicate Code - Language Detection
**File:** `apps/web/components/editor/MonacoEditor.tsx`
**Issue:** `languageFor()` function could be in a shared utility
**Fix:** Move to `lib/utils.ts`

## Orphaned / Unused Code

### 1. Test Script Not Documented
**File:** `apps/api/scripts/test_chat.py`
**Issue:** Exists but not mentioned in README or documented
**Fix:** Add to README or remove if not needed for production

### 2. AGENTS.md File
**File:** `apps/web/AGENTS.md`
**Issue:** Only contains Next.js breaking changes warning
**Fix:** Consider removing or expanding with actual agent documentation

### 3. .venv in Git
**Issue:** Python virtual environment may be partially tracked
**Fix:** Ensure `.venv/` is fully in `.gitignore`

## Missing Features for Production

### 1. No Rate Limiting
**Issue:** No rate limits on API endpoints
**Risk:** DoS, abuse of model APIs
**Fix:** Add rate limiting middleware

### 2. No Request Logging
**Issue:** Minimal logging for security audit
**Fix:** Add structured request/response logging

### 3. No Health Check for Dash Processes
**Issue:** Dash processes detected as "running" if port bound, even if crashed
**Fix:** Implement health check endpoint in Dash apps

### 4. No Cleanup of Orphaned Dash Processes
**Issue:** If API restarts, Dash processes continue running
**Fix:** Add startup cleanup of orphaned processes

### 5. No Database Migrations System
**Issue:** Schema changes use ad-hoc `ALTER TABLE IF NOT EXISTS`
**Fix:** Implement proper migration system (Alembic)

### 6. No Input Validation on File Uploads
**Issue:** No size limits on file writes
**Risk:** Disk exhaustion
**Fix:** Add max file size limits

### 7. No Backup / Export Functionality
**Issue:** No way to export projects or database
**Fix:** Add export/import endpoints

## Deployment Concerns

### 1. Dash Apps on localhost Only
**Issue:** Dash apps bound to `127.0.0.1`, iframe won't work if deployed
**Fix:** Either proxy through backend or add proper authentication

### 2. No HTTPS Enforcement
**Issue:** No redirect to HTTPS
**Fix:** Add HTTPS enforcement middleware

### 3. No CSRF Protection
**Issue:** No CSRF tokens on forms
**Risk:** Cross-site request forgery
**Fix:** Add CSRF protection (FastAPI-CSRF-Protect)

### 4. No Content Security Policy
**Issue:** No CSP headers
**Risk:** XSS attacks
**Fix:** Add CSP middleware

### 5. In Production: No Worker Process Manager
**Issue:** Using `uvicorn` directly without gunicorn/uvicorn workers
**Fix:** Document production deployment with proper process manager

## Documentation Issues

### 1. Missing API Documentation
**Issue:** No public API docs beyond auto-generated FastAPI docs
**Fix:** Add API documentation to README or separate docs site

### 2. No Contributing Guidelines
**Issue:** No CONTRIBUTING.md
**Fix:** Add contribution guidelines

### 3. No License File
**Issue:** README mentions MIT but LICENSE file status unclear
**Fix:** Add LICENSE file if missing

### 4. No Changelog
**Issue:** No CHANGELOG.md
**Fix:** Add changelog for releases

## Frontend Issues

### 1. No Error Boundaries
**Issue:** No React error boundaries
**Risk:** Unhandled crashes show blank screen
**Fix:** Add error boundary components

### 2. No Loading States for Some Operations
**Issue:** Some operations lack visual feedback
**Fix:** Add loading indicators consistently

### 3. No Offline Support
**Issue:** No service worker or offline handling
**Fix:** Consider adding offline support

### 4. Hardcoded "localhost" in Multiple Places
**Issue:** See Critical Security Items #4 above

## Testing Gaps

### 1. No Unit Tests
**Issue:** No test files found
**Fix:** Add unit tests for critical paths

### 2. No Integration Tests
**Issue:** No end-to-end tests
**Fix:** Add integration tests

### 3. Test Script Uses Production-Like Data
**Issue:** `test_chat.py` uses real projects
**Fix:** Use dedicated test environment

## Environment Configuration

### 1. Missing .env.local in .gitignore
**Issue:** `.env.local` is ignored for frontend but `.env.local.example` exists
**Status:** Actually correctly handled - keep as is

### 2. No Validation of Required Env Vars at Startup
**Issue:** App starts even with missing required config
**Fix:** Validate required env vars on startup

### 3. No Distinction Between Dev/Prod Config
**Issue:** Single environment for all modes
**Fix:** Add dev/prod configuration modes

## Performance Concerns

### 1. No Caching
**Issue:** No caching of frequently accessed data
**Fix:** Add caching layer (Redis or in-memory)

### 2. Polling for Logs
**File:** `apps/web/components/dash/DashIframe.tsx`
**Issue:** Polls `/logs` endpoint every second
**Fix:** Use SSE or WebSocket for logs

### 3. No Pagination
**Issue:** Project list, file list, history all unpaginated
**Fix:** Add pagination for large datasets

## Accessibility

### 1. Missing ARIA Labels
**Issue:** Some interactive elements lack ARIA labels
**Fix:** Add ARIA labels throughout

### 2. Keyboard Navigation
**Issue:** May have keyboard navigation gaps
**Fix:** Audit and fix keyboard navigation

## Prioritized Cleanup Summary

### Before Publishing (Must Fix):
1. ✅ Remove default password from test script
2. ✅ Add SESSION_SECRET validation on startup
3. ✅ Document CORS configuration or make it configurable
4. ✅ Consolidate PROTECTED_FILES definitions
5. ✅ Consolidate duplicate git commit functions
6. ✅ Add LICENSE file if missing
7. ✅ Verify .gitignore is complete

### Before Production Use (Should Fix):
1. Add rate limiting
2. Add request logging
3. Implement Dash process health checks
4. Add database migration system
5. Add file size limits
6. Add HTTPS enforcement
7. Add CSRF protection
8. Add CSP headers
9. Document production deployment
10. Add error boundaries

### Nice to Have (Can Defer):
1. Add unit/integration tests
2. Replace polling with SSE for logs
3. Add pagination
4. Add offline support
5. Improve accessibility
6. Add export/import functionality
