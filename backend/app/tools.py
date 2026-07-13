import json
from datetime import datetime, timezone
from typing import Any

from .db import get_connection


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_tool(tool_name: str, input_data: dict[str, Any], output_data: dict[str, Any], status: str = "ok") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO tool_logs (tool_name, input_json, output_json, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tool_name, json.dumps(input_data), json.dumps(output_data), status, utc_now()),
        )


def list_tool_logs(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, tool_name, input_json, output_json, status, created_at
            FROM tool_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "tool_name": row["tool_name"],
            "input": json.loads(row["input_json"]),
            "output": json.loads(row["output_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
