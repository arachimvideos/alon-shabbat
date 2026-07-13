from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def path_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    return Path(raw).expanduser() if raw else default


ALLOWED_ORIGINS = csv_env(
    "ALLOWED_ORIGINS",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)
DATABASE_URL = os.getenv("DATABASE_URL")
DATA_DIR = path_env("DATA_DIR", BASE_DIR / "data")
UPLOADS_DIR = path_env("UPLOADS_DIR", BASE_DIR.parent / "uploads")
DB_PATH = path_env("DB_PATH", DATA_DIR / "articles.db")
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "alon-shabbat-uploads")
