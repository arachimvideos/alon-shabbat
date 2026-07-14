from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def env_value(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1].strip()
    return value


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
DATABASE_URL = env_value("DATABASE_URL")
DATA_DIR = path_env("DATA_DIR", BASE_DIR / "data")
UPLOADS_DIR = path_env("UPLOADS_DIR", BASE_DIR.parent / "uploads")
DB_PATH = path_env("DB_PATH", DATA_DIR / "articles.db")
SUPABASE_URL = env_value("SUPABASE_URL").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = "".join(env_value("SUPABASE_SERVICE_ROLE_KEY").split())
SUPABASE_BUCKET = env_value("SUPABASE_BUCKET", "alon-shabbat-uploads")
ADMIN_PASSWORD = env_value("ADMIN_PASSWORD")
ADMIN_TOKEN_SECRET = env_value("ADMIN_TOKEN_SECRET") or ADMIN_PASSWORD
PDF_FONT_PATH = env_value("PDF_FONT_PATH")
