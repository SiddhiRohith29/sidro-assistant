import re

from .db import get_connection
from .tools import utc_now


def create_note(title: str, content: str) -> dict:
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO notes (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title.strip() or "Untitled note", content.strip(), now, now),
        )
        note_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO notes_fts (title, content, note_id) VALUES (?, ?, ?)",
            (title.strip() or "Untitled note", content.strip(), note_id),
        )
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return dict(row)


def list_notes(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM notes ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def search_notes(query: str, limit: int = 20) -> list[dict]:
    query = query.strip()
    if not query:
        return list_notes(limit)
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    fts_query = " OR ".join(tokens[:12])
    with get_connection() as conn:
        if not fts_query:
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM notes
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        try:
            rows = conn.execute(
                """
                SELECT n.*
                FROM notes_fts f
                JOIN notes n ON n.id = f.note_id
                WHERE notes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        except Exception:
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM notes
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
    return [dict(row) for row in rows]
