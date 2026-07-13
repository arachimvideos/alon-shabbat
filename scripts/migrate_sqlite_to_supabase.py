from __future__ import annotations

import argparse
import mimetypes
import os
import sqlite3
import urllib3
from pathlib import Path
from typing import Any
from urllib.parse import quote

import psycopg
import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_DB = ROOT / "backend" / "data" / "articles.db"
DEFAULT_BUCKET = "alon-shabbat-uploads"

TABLES = ["parashot", "tags", "articles", "article_tags"]

ARTICLE_COLUMNS = [
    "id",
    "title",
    "subtitle",
    "issue_number",
    "parasha_id",
    "author_name",
    "publication_date",
    "uploaded_at",
    "body_text",
    "extracted_text",
    "status",
    "original_filename",
    "stored_filename",
    "file_path",
    "file_type",
    "image_original_filename",
    "image_stored_filename",
    "image_path",
    "image_type",
]


def clean_env_value(name: str) -> str:
    value = os.getenv(name) or ""
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value


def sqlite_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()]


def supabase_config() -> tuple[str, str, str] | None:
    url = clean_env_value("SUPABASE_URL").rstrip("/")
    key = "".join(clean_env_value("SUPABASE_SERVICE_ROLE_KEY").split())
    bucket = clean_env_value("SUPABASE_BUCKET") or DEFAULT_BUCKET
    if not url or not key or not bucket:
        return None
    return url, key, bucket


def supabase_headers(key: str, content_type: str | None = None) -> dict[str, str]:
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def ensure_bucket(url: str, key: str, bucket: str, verify_ssl: bool) -> None:
    response = requests.post(
        f"{url}/storage/v1/bucket",
        headers=supabase_headers(key, "application/json"),
        json={"id": bucket, "name": bucket, "public": False},
        verify=verify_ssl,
        timeout=30,
    )
    if response.status_code not in {200, 201, 409}:
        raise RuntimeError(f"Could not ensure Supabase bucket: {response.status_code} {response.text}")


def upload_object(
    path_value: str | None,
    stored_filename: str | None,
    content_type: str | None,
    verify_ssl: bool,
) -> str | None:
    if not path_value:
        return None
    if path_value.startswith("supabase://"):
        return path_value

    config = supabase_config()
    if config is None:
        return path_value

    source = Path(path_value)
    if not source.exists():
        print(f"warning: file not found, keeping original path: {path_value}")
        return path_value

    url, key, bucket = config
    ensure_bucket(url, key, bucket, verify_ssl)
    object_name = stored_filename or source.name
    upload_url = f"{url}/storage/v1/object/{bucket}/{quote(object_name)}"
    media_type = content_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    data = source.read_bytes()

    response = requests.post(
        upload_url,
        headers=supabase_headers(key, media_type),
        data=data,
        verify=verify_ssl,
        timeout=60,
    )
    if response.status_code == 409:
        response = requests.put(
            upload_url,
            headers=supabase_headers(key, media_type),
            data=data,
            verify=verify_ssl,
            timeout=60,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Could not upload {source.name}: {response.status_code} {response.text}")

    return f"supabase://{bucket}/{object_name}"


def prepare_articles(
    rows: list[dict[str, Any]],
    upload_files: bool,
    verify_storage_ssl: bool,
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        article = {column: row.get(column) for column in ARTICLE_COLUMNS}
        if upload_files:
            article["file_path"] = upload_object(
                article.get("file_path"),
                article.get("stored_filename"),
                article.get("file_type"),
                verify_storage_ssl,
            )
            article["image_path"] = upload_object(
                article.get("image_path"),
                article.get("image_stored_filename"),
                article.get("image_type"),
                verify_storage_ssl,
            )
        prepared.append(article)
    return prepared


def insert_rows(pg: psycopg.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    columns = list(rows[0].keys())
    column_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    if table == "article_tags":
        conflict = "ON CONFLICT (article_id, tag_id) DO NOTHING"
    else:
        updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != "id")
        conflict = f"ON CONFLICT (id) DO UPDATE SET {updates}"

    sql = f"INSERT INTO public.{table} ({column_sql}) VALUES ({placeholders}) {conflict}"
    values = [tuple(row[column] for column in columns) for row in rows]
    with pg.cursor() as cursor:
        cursor.executemany(sql, values)


def reset_sequences(pg: psycopg.Connection) -> None:
    sequence_tables = ["parashot", "tags", "articles"]
    with pg.cursor() as cursor:
        for table in sequence_tables:
            cursor.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('public.{table}', 'id'),
                    GREATEST((SELECT COALESCE(MAX(id), 1) FROM public.{table}), 1),
                    true
                )
                """
            )


def clear_remote(pg: psycopg.Connection) -> None:
    with pg.cursor() as cursor:
        cursor.execute(
            "TRUNCATE public.article_tags, public.articles, public.tags, public.parashot RESTART IDENTITY CASCADE"
        )


def count_remote(pg: psycopg.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    with pg.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM public.{table}")
            counts[table] = int(cursor.fetchone()[0])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_SQLITE_DB)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clear", action="store_true", help="Clear Supabase tables before importing")
    parser.add_argument("--skip-files", action="store_true", help="Do not upload local files to Supabase Storage")
    parser.add_argument(
        "--insecure-storage-ssl",
        action="store_true",
        help="Disable SSL certificate verification for Supabase Storage uploads",
    )
    args = parser.parse_args()

    database_url = clean_env_value("DATABASE_URL")
    if not database_url and not args.dry_run:
        raise RuntimeError("DATABASE_URL is required unless --dry-run is used")

    with sqlite3.connect(args.sqlite_db) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        rows = {table: sqlite_rows(sqlite_conn, table) for table in TABLES}

    print("local counts:", {table: len(table_rows) for table, table_rows in rows.items()})
    if args.dry_run:
        return

    upload_files = not args.skip_files
    if upload_files and supabase_config() is None:
        print("warning: Supabase storage env vars are missing; local file paths will be copied as-is")
    verify_storage_ssl = not args.insecure_storage_ssl
    if not verify_storage_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("warning: SSL verification is disabled for Supabase Storage uploads")

    rows["articles"] = prepare_articles(
        rows["articles"],
        upload_files=upload_files,
        verify_storage_ssl=verify_storage_ssl,
    )

    with psycopg.connect(database_url) as pg:
        if args.clear:
            clear_remote(pg)
        insert_rows(pg, "parashot", rows["parashot"])
        insert_rows(pg, "tags", rows["tags"])
        insert_rows(pg, "articles", rows["articles"])
        insert_rows(pg, "article_tags", rows["article_tags"])
        reset_sequences(pg)
        print("remote counts:", count_remote(pg))


if __name__ == "__main__":
    main()
