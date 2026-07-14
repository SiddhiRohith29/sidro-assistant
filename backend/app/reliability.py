from __future__ import annotations

import json
import shutil
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, DB_PATH, ROOT_DIR, get_settings
from .db import get_connection

BACKUP_DIR = DATA_DIR / "backups"
REQUIRED_TABLES = {
    "conversations",
    "messages",
    "memories",
    "memory_suggestions",
    "files",
    "file_chunks",
    "notes",
    "tool_logs",
    "tasks",
    "reminders",
    "schema_migrations",
    "app_state",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_label(label: str | None) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (label or "manual").strip().lower())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:40] or "manual"


def _check_directory(path: Path, label: str) -> dict[str, Any]:
    item = {"name": label, "status": "ok", "path": str(path), "detail": "Ready"}
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".sidro-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        usage = shutil.disk_usage(path)
        item["free_mb"] = round(usage.free / 1024 / 1024)
    except Exception as exc:  # pragma: no cover - defensive local diagnostics
        item.update({"status": "fail", "detail": f"Cannot write here: {exc}"})
    return item


def _table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ["conversations", "messages", "memories", "notes", "files", "tasks", "reminders", "tool_logs"]:
        try:
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.Error:
            counts[table] = -1
    return counts


def _check_database() -> dict[str, Any]:
    item: dict[str, Any] = {"name": "SQLite database", "status": "ok", "path": str(DB_PATH), "detail": "Ready"}
    try:
        with get_connection() as conn:
            quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]
            user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')").fetchall()
            tables = {row["name"] for row in rows}
            missing = sorted(REQUIRED_TABLES - tables)
            item.update(
                {
                    "quick_check": quick_check,
                    "user_version": user_version,
                    "missing_tables": missing,
                    "counts": _table_counts(conn),
                }
            )
            if quick_check != "ok" or missing:
                item["status"] = "fail"
                item["detail"] = "Database integrity or schema check failed."
    except Exception as exc:  # pragma: no cover - defensive local diagnostics
        item.update({"status": "fail", "detail": f"Database check failed: {exc}"})
    return item


def _check_ollama() -> dict[str, Any]:
    current = get_settings()
    item: dict[str, Any] = {
        "name": "Ollama local model",
        "status": "ok",
        "url": current.ollama_base_url,
        "model": current.ollama_model,
        "detail": "Reachable",
    }
    if current.chat_provider not in {"ollama", "auto"}:
        item.update({"status": "warning", "detail": "Ollama is not the active chat provider."})
        return item
    try:
        with urllib.request.urlopen(f"{current.ollama_base_url.rstrip('/')}/api/tags", timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
        models = [model.get("name", "") for model in payload.get("models", [])]
        item["installed_models"] = models[:20]
        if current.ollama_model not in models:
            item.update({"status": "warning", "detail": f"Ollama is reachable, but {current.ollama_model} was not listed."})
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        item.update({"status": "warning", "detail": f"Ollama did not answer quickly: {exc}"})
    return item


def startup_check() -> dict[str, Any]:
    checks = [
        _check_directory(DATA_DIR, "Data folder"),
        _check_directory(DATA_DIR / "uploads", "Uploads folder"),
        _check_directory(DATA_DIR / "audio", "Audio folder"),
        _check_directory(BACKUP_DIR, "Backups folder"),
        _check_database(),
        _check_ollama(),
    ]
    critical_failed = any(check["status"] == "fail" for check in checks)
    warnings = sum(1 for check in checks if check["status"] == "warning")
    recommendations = []
    if critical_failed:
        recommendations.append("Run backup/restore only after fixing the failed database or folder check.")
    if warnings:
        recommendations.append("Warnings do not block Sidro, but the listed item may need attention.")
    if not recommendations:
        recommendations.append("Sidro reliability checks look healthy.")
    return {
        "ok": not critical_failed,
        "phase": 9,
        "generated_at": _now(),
        "root_dir": str(ROOT_DIR),
        "checks": checks,
        "recommendations": recommendations,
    }


def create_backup(label: str | None = None) -> dict[str, Any]:
    if not DB_PATH.exists():
        raise FileNotFoundError("Sidro database does not exist yet. Start Sidro once before creating a backup.")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"sidro-backup-{stamp}-{_safe_label(label)}.sqlite"
    with get_connection() as conn:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        counts = _table_counts(conn)
    shutil.copy2(DB_PATH, backup_path)
    manifest = {
        "filename": backup_path.name,
        "created_at": _now(),
        "size_bytes": backup_path.stat().st_size,
        "label": _safe_label(label),
        "counts": counts,
    }
    backup_path.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest | {"path": str(backup_path)}


def list_backups() -> list[dict[str, Any]]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups: list[dict[str, Any]] = []
    for path in sorted(BACKUP_DIR.glob("sidro-backup-*.sqlite"), reverse=True):
        manifest_path = path.with_suffix(".json")
        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = {}
        backups.append(
            {
                "filename": path.name,
                "created_at": manifest.get("created_at") or datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "size_bytes": path.stat().st_size,
                "label": manifest.get("label", "manual"),
                "counts": manifest.get("counts", {}),
            }
        )
    return backups


def restore_backup(filename: str, confirmed: bool = False) -> dict[str, Any]:
    safe_name = Path(filename).name
    backup_path = BACKUP_DIR / safe_name
    if not safe_name.startswith("sidro-backup-") or backup_path.suffix != ".sqlite":
        raise ValueError("Choose a Sidro backup file created by this app.")
    if not backup_path.exists():
        raise FileNotFoundError("Backup file was not found.")
    if not confirmed:
        return {"requires_confirmation": True, "filename": safe_name, "detail": "Restore will replace the active local database."}
    pre_restore = create_backup("pre-restore")
    shutil.copy2(backup_path, DB_PATH)
    return {"restored": True, "filename": safe_name, "pre_restore_backup": pre_restore["filename"]}
