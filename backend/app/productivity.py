from .db import get_connection
from .tools import utc_now


def _row_to_task(row) -> dict:
    return dict(row)


def create_task(title: str, details: str = "", due_date: str | None = None, source: str = "manual") -> dict:
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, details, due_date, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title.strip(), details.strip(), due_date, source, now, now),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_task(row)


def list_tasks(status: str | None = None, limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(limit, 200))
    with get_connection() as conn:
        if status in {"open", "done"}:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, updated_at DESC
                LIMIT ?
                """,
                (status, safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                ORDER BY status, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    return [_row_to_task(row) for row in rows]


def update_task(task_id: int, status: str | None = None, title: str | None = None, details: str | None = None, due_date: str | None = None) -> dict | None:
    updates = []
    values = []
    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if title is not None:
        updates.append("title = ?")
        values.append(title.strip())
    if details is not None:
        updates.append("details = ?")
        values.append(details.strip())
    if due_date is not None:
        updates.append("due_date = ?")
        values.append(due_date or None)
    if not updates:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None
    updates.append("updated_at = ?")
    values.append(utc_now())
    values.append(task_id)
    with get_connection() as conn:
        cursor = conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row)


def delete_task(task_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cursor.rowcount > 0


def create_reminder(title: str, remind_at: str | None = None, source: str = "manual") -> dict:
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders (title, remind_at, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title.strip(), remind_at, source, now, now),
        )
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_reminders(status: str | None = None, limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(limit, 200))
    with get_connection() as conn:
        if status in {"open", "done"}:
            rows = conn.execute(
                """
                SELECT * FROM reminders
                WHERE status = ?
                ORDER BY CASE WHEN remind_at IS NULL THEN 1 ELSE 0 END, remind_at, updated_at DESC
                LIMIT ?
                """,
                (status, safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM reminders
                ORDER BY status, CASE WHEN remind_at IS NULL THEN 1 ELSE 0 END, remind_at, updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def update_reminder(reminder_id: int, status: str | None = None, title: str | None = None, remind_at: str | None = None) -> dict | None:
    updates = []
    values = []
    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if title is not None:
        updates.append("title = ?")
        values.append(title.strip())
    if remind_at is not None:
        updates.append("remind_at = ?")
        values.append(remind_at or None)
    if not updates:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return dict(row) if row else None
    updates.append("updated_at = ?")
    values.append(utc_now())
    values.append(reminder_id)
    with get_connection() as conn:
        cursor = conn.execute(f"UPDATE reminders SET {', '.join(updates)} WHERE id = ?", values)
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return dict(row)


def delete_reminder(reminder_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    return cursor.rowcount > 0


def today_summary() -> dict:
    open_tasks = list_tasks(status="open", limit=50)
    open_reminders = list_reminders(status="open", limit=50)
    with get_connection() as conn:
        notes_count = conn.execute("SELECT COUNT(*) AS count FROM notes").fetchone()["count"]
        files_count = conn.execute("SELECT COUNT(*) AS count FROM files").fetchone()["count"]
        memories_count = conn.execute("SELECT COUNT(*) AS count FROM memories").fetchone()["count"]
    return {
        "open_tasks": open_tasks,
        "open_reminders": open_reminders,
        "counts": {
            "tasks": len(open_tasks),
            "reminders": len(open_reminders),
            "notes": notes_count,
            "files": files_count,
            "memories": memories_count,
        },
    }
