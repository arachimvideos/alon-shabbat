from __future__ import annotations

import shutil
import tempfile
import uuid
import re
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import requests

from .config import ALLOWED_ORIGINS, SUPABASE_BUCKET, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from .extractors import extract_text
from .storage import (
    UPLOADS_DIR,
    article_from_row,
    attach_tags,
    connect,
    get_or_create_tags,
    init_db,
    insert_returning_id,
    normalize_tag_names,
    row_to_dict,
    articles_from_rows,
    utc_now,
)

app = FastAPI(title="מערכת מאמרים לעלון פרשת שבוע")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/parashot")
def list_parashot() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM parashot ORDER BY id").fetchall()
        return [row_to_dict(row) for row in rows]


@app.post("/api/parashot", status_code=201)
def create_parasha(name: str = Form(...)) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=422, detail="שם פרשה הוא שדה חובה")
    with connect() as conn:
        try:
            parasha_id = insert_returning_id(
                conn,
                "INSERT INTO parashot (name, created_at) VALUES (?, ?)",
                (clean_name, utc_now()),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="הפרשה כבר קיימת") from exc
        row = conn.execute("SELECT * FROM parashot WHERE id = ?", (parasha_id,)).fetchone()
        return row_to_dict(row)


@app.get("/api/tags")
def list_tags() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM tags ORDER BY name").fetchall()
        return [row_to_dict(row) for row in rows]


@app.post("/api/tags", status_code=201)
def create_tag(name: str = Form(...)) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=422, detail="שם תגית הוא שדה חובה")
    with connect() as conn:
        try:
            tag_id = insert_returning_id(
                conn,
                "INSERT INTO tags (name, created_at) VALUES (?, ?)",
                (clean_name, utc_now()),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="התגית כבר קיימת") from exc
        row = conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        return row_to_dict(row)


@app.post("/api/articles", status_code=201)
def create_article(
    title: str = Form(...),
    subtitle: str | None = Form(None),
    issue_number: str | None = Form(None),
    parasha_id: int = Form(...),
    author_name: str | None = Form(None),
    publication_date: str | None = Form(None),
    body_text: str | None = Form(None),
    tags: str | None = Form(None),
    file: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
) -> dict:
    clean_title = title.strip()
    clean_body = (body_text or "").strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="כותרת היא שדה חובה")
    if not clean_body and (not file or not file.filename):
        raise HTTPException(status_code=422, detail="יש להזין טקסט או לצרף קובץ")

    stored_filename = None
    original_filename = None
    file_path = None
    file_type = None
    extracted = ""

    if file and file.filename:
      original_filename, stored_filename, file_path, file_type, extraction_path = save_upload(file, "article")
      extracted = extract_text(extraction_path)

    image_original_filename = None
    image_stored_filename = None
    image_path = None
    image_type = None

    if image and image.filename:
        if image.content_type and not image.content_type.startswith("image/"):
            raise HTTPException(status_code=422, detail="קובץ התמונה חייב להיות בפורמט תמונה")
        image_original_filename, image_stored_filename, image_path, image_type, _ = save_upload(
            image,
            "image",
        )

    with connect() as conn:
        parasha = conn.execute("SELECT id FROM parashot WHERE id = ?", (parasha_id,)).fetchone()
        if not parasha:
            raise HTTPException(status_code=422, detail="הפרשה שנבחרה אינה קיימת")

        article_id = insert_returning_id(
            conn,
            """
            INSERT INTO articles (
                title, subtitle, issue_number, parasha_id, author_name, publication_date, uploaded_at,
                body_text, extracted_text, status, original_filename, stored_filename,
                file_path, file_type, image_original_filename, image_stored_filename,
                image_path, image_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'פורסם', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_title,
                (subtitle or "").strip() or None,
                (issue_number or "").strip() or None,
                parasha_id,
                (author_name or "").strip() or None,
                publication_date or None,
                utc_now(),
                clean_body or None,
                extracted or None,
                original_filename,
                stored_filename,
                file_path,
                file_type,
                image_original_filename,
                image_stored_filename,
                image_path,
                image_type,
            ),
        )
        tag_ids = get_or_create_tags(conn, normalize_tag_names(tags))
        attach_tags(conn, article_id, tag_ids)
        row = conn.execute(article_select_sql() + " WHERE articles.id = ?", (article_id,)).fetchone()
        return article_from_row(conn, row)


@app.get("/api/articles")
def list_articles(
    q: str | None = None,
    parasha_id: int | None = None,
    tags: list[int] = Query(default=[]),
    tag_match: Literal["any", "all"] = "any",
    publication_from: str | None = None,
    publication_to: str | None = None,
    uploaded_from: str | None = None,
    uploaded_to: str | None = None,
    sort_by: Literal["publication_date", "uploaded_at", "parasha", "title"] = "uploaded_at",
    sort_dir: Literal["asc", "desc"] = "desc",
) -> list[dict]:
    where: list[str] = []
    params: list[object] = []

    if q:
        like = f"%{q.strip()}%"
        where.append(
            """
            (
                articles.title LIKE ? OR articles.subtitle LIKE ? OR articles.issue_number LIKE ?
                OR parashot.name LIKE ? OR articles.author_name LIKE ?
                OR articles.original_filename LIKE ? OR articles.body_text LIKE ?
                OR articles.extracted_text LIKE ?
                OR EXISTS (
                    SELECT 1 FROM article_tags atq
                    JOIN tags tq ON tq.id = atq.tag_id
                    WHERE atq.article_id = articles.id AND tq.name LIKE ?
                )
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like])

    if parasha_id:
        where.append("articles.parasha_id = ?")
        params.append(parasha_id)
    if publication_from:
        where.append("articles.publication_date >= ?")
        params.append(publication_from)
    if publication_to:
        where.append("articles.publication_date <= ?")
        params.append(publication_to)
    if uploaded_from:
        where.append("substr(articles.uploaded_at, 1, 10) >= ?")
        params.append(uploaded_from)
    if uploaded_to:
        where.append("substr(articles.uploaded_at, 1, 10) <= ?")
        params.append(uploaded_to)
    if tags:
        placeholders = ",".join("?" for _ in tags)
        comparator = "> 0" if tag_match == "any" else f"= {len(tags)}"
        where.append(
            f"""
            (
                SELECT COUNT(DISTINCT tag_id)
                FROM article_tags
                WHERE article_id = articles.id AND tag_id IN ({placeholders})
            ) {comparator}
            """
        )
        params.extend(tags)

    order_field = {
        "publication_date": "articles.publication_date",
        "uploaded_at": "articles.uploaded_at",
        "parasha": "parashot.name",
        "title": "articles.title",
    }[sort_by]
    order_dir = "ASC" if sort_dir == "asc" else "DESC"
    sql = article_list_select_sql()
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_field} {order_dir}, articles.id DESC"

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        articles = articles_from_rows(conn, rows)
        for article in articles:
            article["body_text"] = text_preview(article.get("body_text"))
            article["extracted_text"] = text_preview(article.get("extracted_text"))
            article["body_preview"] = article["body_text"]
            article["extracted_preview"] = article["extracted_text"]
        return [add_match_sources(article, q) for article in articles]


@app.get("/api/articles/{article_id}")
def get_article(article_id: int) -> dict:
    with connect() as conn:
        row = conn.execute(article_select_sql() + " WHERE articles.id = ?", (article_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="המאמר לא נמצא")
        return article_from_row(conn, row)


@app.post("/api/articles/{article_id}")
@app.put("/api/articles/{article_id}")
def update_article(
    article_id: int,
    title: str = Form(...),
    subtitle: str | None = Form(None),
    issue_number: str | None = Form(None),
    parasha_id: int = Form(...),
    author_name: str | None = Form(None),
    publication_date: str | None = Form(None),
    body_text: str | None = Form(None),
    tags: str | None = Form(None),
    file: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
) -> dict:
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="כותרת היא שדה חובה")

    clean_body = (body_text or "").strip() or None
    stored_filename = None
    original_filename = None
    file_path = None
    file_type = None
    extracted = None

    if file and file.filename:
        original_filename, stored_filename, file_path, file_type, extraction_path = save_upload(file, "article")
        extracted = extract_text(extraction_path) or None

    image_original_filename = None
    image_stored_filename = None
    image_path = None
    image_type = None

    if image and image.filename:
        if image.content_type and not image.content_type.startswith("image/"):
            raise HTTPException(status_code=422, detail="קובץ התמונה חייב להיות בפורמט תמונה")
        image_original_filename, image_stored_filename, image_path, image_type, _ = save_upload(
            image,
            "image",
        )

    with connect() as conn:
        existing = conn.execute("SELECT id FROM articles WHERE id = ?", (article_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="המאמר לא נמצא")

        parasha = conn.execute("SELECT id FROM parashot WHERE id = ?", (parasha_id,)).fetchone()
        if not parasha:
            raise HTTPException(status_code=422, detail="הפרשה שנבחרה אינה קיימת")

        updates = [
            "title = ?",
            "subtitle = ?",
            "issue_number = ?",
            "parasha_id = ?",
            "author_name = ?",
            "publication_date = ?",
            "body_text = ?",
        ]
        params: list[object] = [
            clean_title,
            (subtitle or "").strip() or None,
            (issue_number or "").strip() or None,
            parasha_id,
            (author_name or "").strip() or None,
            publication_date or None,
            clean_body,
        ]

        if file and file.filename:
            updates.extend(
                [
                    "original_filename = ?",
                    "stored_filename = ?",
                    "file_path = ?",
                    "file_type = ?",
                    "extracted_text = ?",
                ]
            )
            params.extend([original_filename, stored_filename, file_path, file_type, extracted])

        if image and image.filename:
            updates.extend(
                [
                    "image_original_filename = ?",
                    "image_stored_filename = ?",
                    "image_path = ?",
                    "image_type = ?",
                ]
            )
            params.extend([image_original_filename, image_stored_filename, image_path, image_type])

        params.append(article_id)
        conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params)
        conn.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
        tag_ids = get_or_create_tags(conn, normalize_tag_names(tags))
        attach_tags(conn, article_id, tag_ids)

        row = conn.execute(article_select_sql() + " WHERE articles.id = ?", (article_id,)).fetchone()
        return article_from_row(conn, row)


@app.get("/api/articles/{article_id}/file")
def download_article_file(article_id: int) -> Response:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT file_path, original_filename, stored_filename
            FROM articles
            WHERE id = ?
            """,
            (article_id,),
        ).fetchone()
        if not row or not row["file_path"]:
            raise HTTPException(status_code=404, detail="File was not found for this article")
        if is_supabase_path(row["file_path"]):
            content = download_supabase_object(row["file_path"])
            return Response(
                content,
                media_type="application/octet-stream",
                headers={"Content-Disposition": content_disposition(row["original_filename"])},
            )
        path = Path(row["file_path"])
        if not path.exists():
            if use_supabase_storage() and row["stored_filename"]:
                content = download_supabase_object(supabase_object_path(row["stored_filename"]))
                return Response(
                    content,
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": content_disposition(row["original_filename"])},
                )
            raise HTTPException(status_code=404, detail="File was not found on disk")
        return FileResponse(path, filename=row["original_filename"])


@app.get("/api/articles/{article_id}/image")
def download_article_image(article_id: int) -> Response:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT image_path, image_original_filename, image_stored_filename, image_type
            FROM articles
            WHERE id = ?
            """,
            (article_id,),
        ).fetchone()
        if not row or not row["image_path"]:
            raise HTTPException(status_code=404, detail="Image was not found for this article")
        if is_supabase_path(row["image_path"]):
            content = download_supabase_object(row["image_path"])
            return Response(
                content,
                media_type=row["image_type"] or "application/octet-stream",
                headers={"Content-Disposition": inline_content_disposition(row["image_original_filename"])},
            )
        path = Path(row["image_path"])
        if not path.exists():
            if use_supabase_storage() and row["image_stored_filename"]:
                content = download_supabase_object(supabase_object_path(row["image_stored_filename"]))
                return Response(
                    content,
                    media_type=row["image_type"] or "application/octet-stream",
                    headers={"Content-Disposition": inline_content_disposition(row["image_original_filename"])},
                )
            raise HTTPException(status_code=404, detail="Image was not found on disk")
        return FileResponse(
            path,
            media_type=row["image_type"] or None,
            filename=row["image_original_filename"],
        )

def save_upload(upload: UploadFile, prefix: str) -> tuple[str, str, str, str, Path]:
    original_filename = Path(upload.filename or "upload").name
    suffix = Path(original_filename).suffix
    stored_filename = f"{prefix}-{uuid.uuid4().hex}{suffix}"
    content_type = upload.content_type or "application/octet-stream"
    data = upload.file.read()

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp.write(data)
    temp.close()
    extraction_path = Path(temp.name)

    if use_supabase_storage():
        ensure_supabase_bucket()
        file_path = upload_supabase_object(stored_filename, data, content_type)
    else:
        destination = UPLOADS_DIR / stored_filename
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as buffer:
            buffer.write(data)
        file_path = str(destination)

    return (
        original_filename,
        stored_filename,
        file_path,
        content_type,
        extraction_path,
    )


def use_supabase_storage() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_BUCKET)


_supabase_bucket_ready = False


def ensure_supabase_bucket() -> None:
    global _supabase_bucket_ready
    if not use_supabase_storage():
        return
    if _supabase_bucket_ready:
        return
    existing = requests.get(
        f"{SUPABASE_URL}/storage/v1/bucket/{SUPABASE_BUCKET}",
        headers=supabase_headers(),
        timeout=10,
    )
    if existing.status_code == 200:
        _supabase_bucket_ready = True
        return

    url = f"{SUPABASE_URL}/storage/v1/bucket"
    response = requests.post(
        url,
        headers={**supabase_headers("application/json")},
        json={"id": SUPABASE_BUCKET, "name": SUPABASE_BUCKET, "public": False},
        timeout=10,
    )
    if response.status_code in {200, 201, 409}:
        _supabase_bucket_ready = True
        return
    detail = response.text[:300]
    raise RuntimeError(f"Supabase storage bucket setup failed: {response.status_code} {detail}")


def supabase_headers(content_type: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def upload_supabase_object(stored_filename: str, data: bytes, content_type: str) -> str:
    encoded_name = quote(stored_filename)
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{encoded_name}"
    response = requests.post(url, headers=supabase_headers(content_type), data=data, timeout=30)
    if response.status_code == 409:
        response = requests.put(url, headers=supabase_headers(content_type), data=data, timeout=30)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Supabase storage upload failed")
    return f"supabase://{SUPABASE_BUCKET}/{stored_filename}"


def supabase_object_path(stored_filename: str) -> str:
    return f"supabase://{SUPABASE_BUCKET}/{stored_filename}"

def is_supabase_path(path: str | None) -> bool:
    return bool(path and path.startswith("supabase://"))


def download_supabase_object(path: str) -> bytes:
    _, rest = path.split("://", 1)
    bucket, object_name = rest.split("/", 1)
    encoded_name = quote(object_name)
    urls = [
        f"{SUPABASE_URL}/storage/v1/object/{bucket}/{encoded_name}",
        f"{SUPABASE_URL}/storage/v1/object/authenticated/{bucket}/{encoded_name}",
        f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{encoded_name}",
    ]
    response = None
    for url in urls:
        response = requests.get(url, headers=supabase_headers(), timeout=30)
        if response.status_code < 400:
            break
        if response.status_code != 404:
            detail = response.text[:300] if response.text else response.reason
            print(f"warning: Supabase storage download attempt failed: {response.status_code} {detail}")
    if response is None:
        raise HTTPException(status_code=502, detail="Supabase storage download failed")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="הקובץ לא נמצא באחסון")
    if response.status_code >= 400:
        detail = response.text[:300] if response.text else response.reason
        print(f"warning: Supabase storage download failed: {response.status_code} {detail}")
        raise HTTPException(
            status_code=502,
            detail=f"Supabase storage download failed: {response.status_code}",
        )
    return response.content


def content_disposition(filename: str | None) -> str:
    safe_name = filename or "download"
    return f"attachment; filename*=UTF-8''{quote(safe_name)}"


def inline_content_disposition(filename: str | None) -> str:
    safe_name = filename or "image"
    return f"inline; filename*=UTF-8''{quote(safe_name)}"

def article_select_sql() -> str:
    return """
        SELECT
            articles.*,
            parashot.name AS parasha_name
        FROM articles
        JOIN parashot ON parashot.id = articles.parasha_id
    """


def article_list_select_sql() -> str:
    return """
        SELECT
            articles.id,
            articles.title,
            articles.subtitle,
            articles.issue_number,
            articles.parasha_id,
            articles.author_name,
            articles.publication_date,
            articles.uploaded_at,
            substr(articles.body_text, 1, 1200) AS body_text,
            substr(articles.extracted_text, 1, 1200) AS extracted_text,
            substr(articles.body_text, 1, 1200) AS body_preview,
            substr(articles.extracted_text, 1, 1200) AS extracted_preview,
            articles.status,
            articles.original_filename,
            articles.stored_filename,
            articles.file_path,
            articles.file_type,
            articles.image_original_filename,
            articles.image_stored_filename,
            articles.image_path,
            articles.image_type,
            parashot.name AS parasha_name
        FROM articles
        JOIN parashot ON parashot.id = articles.parasha_id
    """


def text_preview(value: object, limit: int = 260) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def add_match_sources(article: dict, q: str | None) -> dict:
    if not q:
        article["match_sources"] = []
        return article

    term = q.casefold().strip()
    sources: list[str] = []
    checks = [
        ("כותרת", article.get("title")),
        ("כותרת משנה", article.get("subtitle")),
        ("מספר גיליון", article.get("issue_number")),
        ("פרשה", article.get("parasha_name")),
        ("מחבר", article.get("author_name")),
        ("שם קובץ", article.get("original_filename")),
        ("גוף המאמר", article.get("body_preview") or article.get("body_text")),
        ("טקסט שחולץ", article.get("extracted_preview") or article.get("extracted_text")),
    ]
    for label, value in checks:
        if value and term in str(value).casefold():
            sources.append(label)
    if any(term in tag["name"].casefold() for tag in article.get("tags", [])):
        sources.append("תגית")
    article["match_sources"] = sources
    return article

