"""Environment-driven settings for the API."""
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]


def _abs(value: str) -> str:
    """Resolve a path relative to the repo root when it's not already absolute."""
    p = Path(value)
    return str(p if p.is_absolute() else (ROOT / p).resolve())


class Settings(BaseSettings):
    """Runtime configuration pulled from the repo-root `.env`."""

    admin_username: str = "admin"
    admin_password: str = ""
    duckdb_path: str = str(ROOT / "data" / "metadata.duckdb")
    projects_root: str = str(ROOT / "projects")
    template_dash: str = str(ROOT / "templates" / "dash_app.py")
    api_port: int = 8000
    session_secret: str = "change-me"
    dash_port_range_start: int = 8100

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("duckdb_path", "projects_root", "template_dash")
    @classmethod
    def _absolutize(cls, v: str) -> str:
        """Normalize path settings to absolute paths anchored at the repo root."""
        return _abs(v)


settings = Settings()
