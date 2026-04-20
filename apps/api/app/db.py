"""DuckDB connection and schema bootstrap."""
from pathlib import Path
import duckdb
import time

from .settings import settings


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
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

CREATE TABLE IF NOT EXISTS model_configs (
    id TEXT PRIMARY KEY,
    label TEXT UNIQUE NOT NULL,
    model TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key_env TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


# Shared connection for better concurrency
_shared_con = None


def connect() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with retry logic for concurrent access."""
    global _shared_con
    Path(settings.duckdb_path).parent.mkdir(parents=True, exist_ok=True)

    # Retry logic for concurrent access
    max_retries = 3
    for attempt in range(max_retries):
        try:
            con = duckdb.connect(settings.duckdb_path, read_only=False)
            con.execute(_SCHEMA)
            # Migration: add current_commit column if not exists
            try:
                con.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS current_commit TEXT")
            except Exception:
                pass  # Column may already exist
            return con
        except duckdb.BinderException as e:
            if "already attached" in str(e) and attempt < max_retries - 1:
                time.sleep(0.01 * (attempt + 1))  # Exponential backoff
                continue
            raise
    return duckdb.connect(settings.duckdb_path)
