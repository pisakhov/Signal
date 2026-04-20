"""FastAPI entry point wiring auth, projects, and chat routers."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import ensure_admin_seed
from .chat import router as chat_router
from .projects import router as projects_router
from .routers_auth import router as auth_router
from .routers_models import router as models_router
from .runner import cleanup_orphans
from .settings import settings
from .middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    LoggingMiddleware,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Quant Investment Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (before other middleware to count all requests)
app.add_middleware(RateLimitMiddleware)

# Security headers (must be after CORS)
app.add_middleware(SecurityHeadersMiddleware)

# Request logging
app.add_middleware(LoggingMiddleware)


@app.on_event("startup")
def _startup() -> None:
    """Seed the admin user on first boot and clean up orphaned processes."""
    ensure_admin_seed()
    cleanup_orphans()


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(chat_router)
app.include_router(models_router)
