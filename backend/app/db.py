import sqlite3
from pathlib import Path

from .config import DATA_DIR, DB_PATH


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "audio").mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                category TEXT NOT NULL DEFAULT 'general',
                sensitivity TEXT NOT NULL DEFAULT 'normal' CHECK(sensitivity IN ('normal', 'private')),
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'dismissed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS file_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS file_chunks_fts
            USING fts5(content, file_id UNINDEXED, chunk_id UNINDEXED, filename UNINDEXED);

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
            USING fts5(title, content, note_id UNINDEXED);

            CREATE TABLE IF NOT EXISTS tool_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                input_json TEXT NOT NULL,
                output_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'done')),
                due_date TEXT,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                remind_at TEXT,
                status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'done')),
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, created_at);

            CREATE INDEX IF NOT EXISTS idx_file_chunks_file
            ON file_chunks(file_id, chunk_index);
            CREATE INDEX IF NOT EXISTS idx_tasks_status_due
            ON tasks(status, due_date);

            CREATE INDEX IF NOT EXISTS idx_reminders_status_time
            ON reminders(status, remind_at);

            CREATE INDEX IF NOT EXISTS idx_memories_category
            ON memories(category, sensitivity);

            CREATE INDEX IF NOT EXISTS idx_memory_suggestions_status
            ON memory_suggestions(status, created_at);
            """
        )

        memory_columns = {row["name"] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "category" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN category TEXT NOT NULL DEFAULT 'general'")
        if "sensitivity" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'normal'")
        if "pinned" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        if "updated_at" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN updated_at TEXT")
            conn.execute("UPDATE memories SET updated_at = created_at WHERE updated_at IS NULL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'dismissed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def db_path() -> Path:
    return DB_PATH
