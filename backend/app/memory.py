from .db import get_connection
from .tools import utc_now


def create_memory(content: str, source: str = "manual") -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO memories (content, source, created_at) VALUES (?, ?, ?)",
            (content.strip(), source, utc_now()),
        )
        memory_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return dict(row)


def list_memories() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM memories ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def delete_memory(memory_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0


def search_memories(query: str, limit: int = 6) -> list[dict]:
    words = [word for word in query.lower().split() if len(word) > 2]
    if not words:
        return list_memories()[:limit]
    clauses = " OR ".join(["LOWER(content) LIKE ?" for _ in words])
    params = [f"%{word}%" for word in words]
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM memories WHERE {clauses} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [dict(row) for row in rows]
