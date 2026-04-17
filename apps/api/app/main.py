"""FastAPI entry point wiring auth, projects, and chat routers."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import ensure_admin_seed
from .chat import router as chat_router
from .projects import router as projects_router
from .routers_auth import router as auth_router
from .routers_models import router as models_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Quant Investment Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    """Seed the admin user on first boot."""
    ensure_admin_seed()


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(chat_router)
app.include_router(models_router)
