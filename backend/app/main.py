from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import ALLOWED_ORIGINS
from .extractors import extract_text
from .storage import (
    UPLOADS_DIR,
    article_from_row,
    attach_tags,
    connect,
    get_or_create_tags,
    init_db,
    normalize_tag_names,
    row_to_dict,
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
            cursor = conn.execute(
                "INSERT INTO parashot (name, created_at) VALUES (?, ?)",
                (clean_name, utc_now()),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="הפרשה כבר קיימת") from exc
        row = conn.execute("SELECT * FROM parashot WHERE id = ?", (cursor.lastrowid,)).fetchone()
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
            cursor = conn.execute(
                "INSERT INTO tags (name, created_at) VALUES (?, ?)",
                (clean_name, utc_now()),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="התגית כבר קיימת") from exc
        row = conn.execute("SELECT * FROM tags WHERE id = ?", (cursor.lastrowid,)).fetchone()
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
      original_filename, stored_filename, file_path, file_type = save_upload(file, "article")
      extracted = extract_text(Path(file_path))

    image_original_filename = None
    image_stored_filename = None
    image_path = None
    image_type = None

    if image and image.filename:
        if image.content_type and not image.content_type.startswith("image/"):
            raise HTTPException(status_code=422, detail="קובץ התמונה חייב להיות בפורמט תמונה")
        image_original_filename, image_stored_filename, image_path, image_type = save_upload(
            image,
            "image",
        )

    with connect() as conn:
        parasha = conn.execute("SELECT id FROM parashot WHERE id = ?", (parasha_id,)).fetchone()
        if not parasha:
            raise HTTPException(status_code=422, detail="הפרשה שנבחרה אינה קיימת")

        cursor = conn.execute(
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
        article_id = int(cursor.lastrowid)
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
        where.append("date(articles.uploaded_at) >= ?")
        params.append(uploaded_from)
    if uploaded_to:
        where.append("date(articles.uploaded_at) <= ?")
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
    sql = article_select_sql()
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_field} {order_dir}, articles.id DESC"

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        articles = [article_from_row(conn, row) for row in rows]
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
        original_filename, stored_filename, file_path, file_type = save_upload(file, "article")
        extracted = extract_text(Path(file_path)) or None

    image_original_filename = None
    image_stored_filename = None
    image_path = None
    image_type = None

    if image and image.filename:
        if image.content_type and not image.content_type.startswith("image/"):
            raise HTTPException(status_code=422, detail="קובץ התמונה חייב להיות בפורמט תמונה")
        image_original_filename, image_stored_filename, image_path, image_type = save_upload(
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
def download_article_file(article_id: int) -> FileResponse:
    with connect() as conn:
        row = conn.execute(
            "SELECT file_path, original_filename FROM articles WHERE id = ?",
            (article_id,),
        ).fetchone()
        if not row or not row["file_path"]:
            raise HTTPException(status_code=404, detail="לא נמצא קובץ למאמר")
        path = Path(row["file_path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail="הקובץ לא נמצא בדיסק")
        return FileResponse(path, filename=row["original_filename"])


@app.get("/api/articles/{article_id}/image")
def download_article_image(article_id: int) -> FileResponse:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT image_path, image_original_filename, image_type
            FROM articles
            WHERE id = ?
            """,
            (article_id,),
        ).fetchone()
        if not row or not row["image_path"]:
            raise HTTPException(status_code=404, detail="לא נמצאה תמונה למאמר")
        path = Path(row["image_path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail="התמונה לא נמצאה בדיסק")
        return FileResponse(
            path,
            media_type=row["image_type"] or None,
            filename=row["image_original_filename"],
        )


def save_upload(upload: UploadFile, prefix: str) -> tuple[str, str, str, str]:
    original_filename = Path(upload.filename or "upload").name
    suffix = Path(original_filename).suffix
    stored_filename = f"{prefix}-{uuid.uuid4().hex}{suffix}"
    destination = UPLOADS_DIR / stored_filename
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return (
        original_filename,
        stored_filename,
        str(destination),
        upload.content_type or "application/octet-stream",
    )


def article_select_sql() -> str:
    return """
        SELECT
            articles.*,
            parashot.name AS parasha_name
        FROM articles
        JOIN parashot ON parashot.id = articles.parasha_id
    """


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
        ("גוף המאמר", article.get("body_text")),
        ("טקסט שחולץ", article.get("extracted_text")),
    ]
    for label, value in checks:
        if value and term in str(value).casefold():
            sources.append(label)
    if any(term in tag["name"].casefold() for tag in article.get("tags", [])):
        sources.append("תגית")
    article["match_sources"] = sources
    return article
