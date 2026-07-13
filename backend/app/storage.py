from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import DATA_DIR, DB_PATH, UPLOADS_DIR
from .parashot import DEFAULT_PARASHOT


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS parashot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subtitle TEXT,
                issue_number TEXT,
                parasha_id INTEGER NOT NULL REFERENCES parashot(id),
                author_name TEXT,
                publication_date TEXT,
                uploaded_at TEXT NOT NULL,
                body_text TEXT,
                extracted_text TEXT,
                status TEXT NOT NULL DEFAULT 'פורסם',
                original_filename TEXT,
                stored_filename TEXT,
                file_path TEXT,
                file_type TEXT,
                image_original_filename TEXT,
                image_stored_filename TEXT,
                image_path TEXT,
                image_type TEXT
            );

            CREATE TABLE IF NOT EXISTS article_tags (
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (article_id, tag_id)
            );
            """
        )
        ensure_article_columns(conn)
        now = utc_now()
        conn.executemany(
            "INSERT OR IGNORE INTO parashot (name, created_at) VALUES (?, ?)",
            [(name, now) for name in DEFAULT_PARASHOT],
        )
        conn.executemany(
            "UPDATE parashot SET name = ? WHERE id = ?",
            [(name, index + 1) for index, name in enumerate(DEFAULT_PARASHOT)],
        )


def ensure_article_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
    migrations = {
        "subtitle": "ALTER TABLE articles ADD COLUMN subtitle TEXT",
        "issue_number": "ALTER TABLE articles ADD COLUMN issue_number TEXT",
        "image_original_filename": "ALTER TABLE articles ADD COLUMN image_original_filename TEXT",
        "image_stored_filename": "ALTER TABLE articles ADD COLUMN image_stored_filename TEXT",
        "image_path": "ALTER TABLE articles ADD COLUMN image_path TEXT",
        "image_type": "ALTER TABLE articles ADD COLUMN image_type TEXT",
    }
    for column, statement in migrations.items():
        if column not in columns:
            conn.execute(statement)


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def normalize_tag_names(raw: str | None) -> list[str]:
    if not raw:
        return []
    names = [part.strip() for part in re.split(r"[,;\n]+", raw) if part.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(name)
    return unique


def get_or_create_tags(conn: sqlite3.Connection, names: list[str]) -> list[int]:
    ids: list[int] = []
    now = utc_now()
    for name in names:
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, created_at) VALUES (?, ?)",
            (name, now),
        )
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if row:
            ids.append(int(row["id"]))
    return ids


def attach_tags(conn: sqlite3.Connection, article_id: int, tag_ids: list[int]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO article_tags (article_id, tag_id) VALUES (?, ?)",
        [(article_id, tag_id) for tag_id in tag_ids],
    )


def load_article_tags(conn: sqlite3.Connection, article_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT tags.id, tags.name
        FROM tags
        JOIN article_tags ON article_tags.tag_id = tags.id
        WHERE article_tags.article_id = ?
        ORDER BY tags.name
        """,
        (article_id,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def article_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    article = row_to_dict(row)
    article["tags"] = load_article_tags(conn, int(article["id"]))
    return article
