import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import DATA_DIR
from .db import get_connection
from .tools import utc_now

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def _clean_fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    return " OR ".join(tokens[:12])


def _chunks(text: str, size: int = 1400, overlap: int = 180) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + size, len(cleaned))
        chunks.append(cleaned[start:end])
        start = max(end - overlap, end) if end == len(cleaned) else end - overlap
    return chunks


def _extract_text(path: Path, suffix: str, raw: bytes) -> str:
    if suffix in {".txt", ".md"}:
        return raw.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        from docx import Document

        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise ValueError(f"Unsupported file type: {suffix}")


async def index_upload(upload: UploadFile) -> dict:
    filename = upload.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only .txt, .md, .pdf, and .docx files are supported.")

    raw = await upload.read()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = DATA_DIR / "uploads" / stored_name
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_bytes(raw)

    text = _extract_text(stored_path, suffix, raw)
    chunks = _chunks(text)
    if not chunks:
        raise ValueError("No readable text was found in that file.")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO files (filename, stored_path, content_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (filename, str(stored_path), upload.content_type, len(raw), utc_now()),
        )
        file_id = cursor.lastrowid
        for index, chunk in enumerate(chunks):
            chunk_cursor = conn.execute(
                "INSERT INTO file_chunks (file_id, chunk_index, content) VALUES (?, ?, ?)",
                (file_id, index, chunk),
            )
            chunk_id = chunk_cursor.lastrowid
            conn.execute(
                "INSERT INTO file_chunks_fts (content, file_id, chunk_id, filename) VALUES (?, ?, ?, ?)",
                (chunk, file_id, chunk_id, filename),
            )
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    result = dict(row)
    result["chunk_count"] = len(chunks)
    return result


def list_files() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.*, COUNT(c.id) AS chunk_count
            FROM files f
            LEFT JOIN file_chunks c ON c.file_id = f.id
            GROUP BY f.id
            ORDER BY f.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def search_files(query: str, limit: int = 8) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    fts_query = _clean_fts_query(query)
    with get_connection() as conn:
        if fts_query:
            try:
                rows = conn.execute(
                    """
                    SELECT f.id AS file_id, f.filename, c.id AS chunk_id, c.chunk_index, c.content
                    FROM file_chunks_fts x
                    JOIN file_chunks c ON c.id = x.chunk_id
                    JOIN files f ON f.id = c.file_id
                    WHERE file_chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
                return [dict(row) for row in rows]
            except Exception:
                pass
        like = f"%{query}%"
        rows = conn.execute(
            """
            SELECT f.id AS file_id, f.filename, c.id AS chunk_id, c.chunk_index, c.content
            FROM file_chunks c
            JOIN files f ON f.id = c.file_id
            WHERE c.content LIKE ? OR f.filename LIKE ?
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (like, like, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_file_chunks(file_id: int, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.filename, c.chunk_index, c.content
            FROM file_chunks c
            JOIN files f ON f.id = c.file_id
            WHERE f.id = ?
            ORDER BY c.chunk_index
            LIMIT ?
            """,
            (file_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def latest_file_id() -> int | None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM files ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None
