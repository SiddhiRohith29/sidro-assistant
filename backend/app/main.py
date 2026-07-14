import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import ai, files, memory, notes, productivity, quality, reliability, voice
from .config import DATA_DIR, SIDRO_SYSTEM_PROMPT, get_settings
from .db import get_connection, init_db
from .language import detect_language
from .tools import list_tool_logs, log_tool, utc_now

app = FastAPI(title="Sidro v1")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin, "http://127.0.0.1:5173"],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    use_file_context: bool = True
    memory_enabled: bool = True


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = None
    language: str | None = None


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1)
    category: str | None = None
    sensitivity: str = "normal"
    pinned: bool = False


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    category: str | None = None
    sensitivity: str | None = None
    pinned: bool | None = None


class MemoryMergeRequest(BaseModel):
    memory_ids: list[int] = Field(min_length=2)
    content: str = Field(min_length=1)
    category: str | None = None
    sensitivity: str = "normal"
    pinned: bool = False


class MemorySuggestionRequest(BaseModel):
    content: str = Field(min_length=1)
    reason: str = "Manual suggestion"
    category: str | None = None


class MemorySuggestionAcceptRequest(BaseModel):
    pinned: bool = False
    sensitivity: str = "normal"


class NoteRequest(BaseModel):
    title: str = "Untitled note"
    content: str = Field(min_length=1)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


class ContextPreviewRequest(BaseModel):
    query: str = Field(min_length=1)
    use_file_context: bool = True
    memory_enabled: bool = True


class ConversationTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
class TaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    details: str = ""
    due_date: str | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    details: str | None = None
    due_date: str | None = None
    status: str | None = None


class ReminderRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    remind_at: str | None = None


class ReminderUpdateRequest(BaseModel):
    title: str | None = None
    remind_at: str | None = None
    status: str | None = None


class LocalFileRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content: str = ""
    confirmed: bool = False


class BackupRequest(BaseModel):
    label: str | None = None


class RestoreBackupRequest(BaseModel):
    filename: str = Field(min_length=1)
    confirmed: bool = False


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Sidro could not understand this request. Check the required fields and try again.",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Sidro hit a local backend error. Run the reliability check, then restart the backend if needed.",
            "error_type": exc.__class__.__name__,
        },
    )


@app.get("/api/health")
def health() -> dict:
    current = get_settings()
    return {
        "ok": True,
        "api_key_configured": bool(current.openai_api_key),
        "chat_provider": current.chat_provider,
        "ollama_base_url": current.ollama_base_url,
        "stt_provider": current.stt_provider,
        "tts_provider": current.tts_provider,
        "db": "ready",
        "quality_phase": 6,
        "roadmap_complete_phase": 9,
    }


@app.get("/api/settings")
def read_settings() -> dict:
    current = get_settings()
    return {
        "api_key_configured": bool(current.openai_api_key),
        "chat_provider": current.chat_provider,
        "chat_model": current.chat_model,
        "ollama_base_url": current.ollama_base_url,
        "ollama_model": current.ollama_model,
        "ollama_num_predict": current.ollama_num_predict,
        "ollama_num_ctx": current.ollama_num_ctx,
        "stt_provider": current.stt_provider,
        "faster_whisper_model": current.faster_whisper_model,
        "faster_whisper_device": current.faster_whisper_device,
        "tts_provider": current.tts_provider,
        "piper_configured": bool(current.piper_exe and current.piper_model),
        "transcription_model": current.transcription_model,
        "tts_model": current.tts_model,
        "tts_voice": current.tts_voice,
        "voices": ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"],
        "ui_phase": 8,
        "keyboard_shortcuts": [
            {"keys": "Ctrl+K", "action": "Focus chat composer"},
            {"keys": "Ctrl+N", "action": "Start new chat"},
            {"keys": "Ctrl+B", "action": "Start brainstorming chat"},
            {"keys": "Escape", "action": "Stop response or close active draft"},
        ],
        "accessibility": {
            "skip_link": True,
            "landmarks": True,
            "live_status": True,
            "responsive_mobile_nav": True,
        },
        "reliability_phase": 9,
        "reliability_features": ["startup_check", "backup", "restore_preview", "migration_safety", "friendly_errors", "one_click_launcher"],
    }


@app.get("/api/reliability/startup-check")
def reliability_startup_check() -> dict:
    return reliability.startup_check()


@app.get("/api/reliability/backups")
def reliability_backups() -> list[dict]:
    return reliability.list_backups()


@app.post("/api/reliability/backups")
def reliability_create_backup(request: BackupRequest) -> dict:
    try:
        return reliability.create_backup(request.label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/reliability/restore")
def reliability_restore_backup(request: RestoreBackupRequest) -> dict:
    try:
        return reliability.restore_backup(request.filename, request.confirmed)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _create_conversation(title: str) -> str:
    conversation_id = str(uuid.uuid4())
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conversation_id, title[:80] or "Sidro chat", now, now),
        )
    return conversation_id


def _touch_conversation(conversation_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (utc_now(), conversation_id))


def _save_message(conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, role, content, json.dumps(metadata or {}), utc_now()),
        )
    _touch_conversation(conversation_id)


def _recent_messages(conversation_id: str, limit: int = 20) -> list[dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def _context_summary(remembered: list[dict] | None = None, file_hits: list[dict] | None = None) -> dict[str, Any]:
    memory_items = [
        {
            "id": item.get("id"),
            "content": item.get("content", ""),
            "score": item.get("match_score"),
        }
        for item in (remembered or [])
    ]
    file_items = []
    seen_chunks: set[Any] = set()
    for hit in file_hits or []:
        chunk_id = hit.get("chunk_id")
        if chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)
        file_items.append(
            {
                "citation": f"F{len(file_items) + 1}",
                "file_id": hit.get("file_id"),
                "filename": hit.get("filename", "Uploaded file"),
                "chunk_id": chunk_id,
                "chunk_index": hit.get("chunk_index"),
                "snippet": (hit.get("content", "")[:180]).strip(),
            }
        )
    return {
        "memory_count": len(memory_items),
        "file_count": len(file_items),
        "memories": memory_items,
        "files": file_items,
    }


def _append_file_sources(reply: str, context_summary: dict[str, Any]) -> str:
    files_used = context_summary.get("files") or []
    if not files_used:
        return reply
    if "sources:" in reply.lower():
        return reply
    lines = []
    for source in files_used[:5]:
        label = source.get("citation", "F?")
        filename = source.get("filename", "Uploaded file")
        chunk = source.get("chunk_index")
        lines.append(f"[{label}] {filename}, chunk {chunk}")
    return reply.rstrip() + "\n\nSources:\n" + "\n".join(lines)


def _chat_response(
    conversation_id: str,
    reply: str,
    tool_activities: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    used_file_context: bool = False,
    used_memory_context: bool = False,
    context_summary: dict[str, Any] | None = None,
) -> dict:
    summary = context_summary or _context_summary()
    _save_message(
        conversation_id,
        "assistant",
        reply,
        {
            "tool_activities": tool_activities or [],
            "actions": actions or [],
            "used_file_context": used_file_context,
            "used_memory_context": used_memory_context,
            "context_summary": summary,
        },
    )
    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "language": detect_language(reply),
        "tool_activities": tool_activities or [],
        "actions": actions or [],
        "used_file_context": used_file_context,
        "used_memory_context": used_memory_context,
        "context_summary": summary,
    }


def _parse_title_details(text: str, prefixes: tuple[str, ...]) -> tuple[str, str]:
    cleaned = text.strip()
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    if ":" in cleaned:
        title, details = cleaned.split(":", 1)
        return title.strip(), details.strip()
    return cleaned, ""

def _parse_note(text: str) -> tuple[str, str]:
    cleaned = re.sub(r"^(create|make|save)\s+(a\s+)?note\s*(that|called|:)?", "", text, flags=re.I).strip()
    if ":" in cleaned:
        title, content = cleaned.split(":", 1)
        return title.strip() or "Chat note", content.strip()
    return "Chat note", cleaned


def _open_url_action(message: str) -> dict[str, Any] | None:
    match = re.search(r"https?://[^\s]+", message)
    if not match:
        return None
    url = match.group(0).rstrip(".,)")
    return {"type": "open_url", "url": url, "label": "Open site"}


def _handle_local_tool(message: str, conversation_id: str) -> dict | None:
    lower = message.lower().strip()

    if lower.startswith("remember that "):
        content = message.strip()[14:].strip()
        item = memory.create_memory(content, source="chat")
        output = {"memory_id": item["id"], "content": item["content"]}
        log_tool("create_memory", {"content": content}, output)
        return _chat_response(
            conversation_id,
            f"Remembered: {item['content']}",
            [{"tool": "create_memory", "status": "saved", "detail": item["content"]}],
        )

    if "what do you remember about me" in lower or lower == "list memories":
        items = memory.list_memories()
        output = {"count": len(items)}
        log_tool("list_memories", {}, output)
        if not items:
            reply = "I do not have any saved memories yet."
        else:
            lines = "\n".join(f"- {item['content']}" for item in items)
            reply = f"Here is what I remember:\n{lines}"
        return _chat_response(conversation_id, reply, [{"tool": "list_memories", "status": "done", "detail": output}])

    if lower.startswith(("create task", "add task", "new task")):
        title, details = _parse_title_details(message, ("create task", "add task", "new task"))
        if not title:
            return _chat_response(conversation_id, "Tell me the task title and I will add it to Today.")
        task = productivity.create_task(title, details=details, source="chat")
        log_tool("create_task", {"title": title}, {"task_id": task["id"]})
        return _chat_response(
            conversation_id,
            f"Task added: {task['title']}",
            [{"tool": "create_task", "status": "created", "detail": {"task_id": task["id"], "title": task["title"]}}],
        )

    if lower in {"list tasks", "show tasks", "today tasks"}:
        items = productivity.list_tasks(status="open", limit=10)
        log_tool("list_tasks", {}, {"count": len(items)})
        reply = "No open tasks yet." if not items else "Open tasks:\n" + "\n".join(f"- #{item['id']} {item['title']}" for item in items)
        return _chat_response(conversation_id, reply, [{"tool": "list_tasks", "status": "done", "detail": {"count": len(items)}}])

    if lower.startswith(("remind me", "create reminder", "add reminder")):
        title, details = _parse_title_details(message, ("remind me", "create reminder", "add reminder"))
        reminder_title = title or details
        if not reminder_title:
            return _chat_response(conversation_id, "Tell me what the Sidro reminder should say.")
        reminder = productivity.create_reminder(reminder_title, source="chat")
        log_tool("create_reminder", {"title": reminder_title}, {"reminder_id": reminder["id"]})
        return _chat_response(
            conversation_id,
            f"Internal Sidro reminder saved: {reminder['title']}",
            [{"tool": "create_reminder", "status": "created", "detail": {"reminder_id": reminder["id"], "title": reminder["title"]}}],
        )

    if lower in {"list reminders", "show reminders"}:
        items = productivity.list_reminders(status="open", limit=10)
        log_tool("list_reminders", {}, {"count": len(items)})
        reply = "No open Sidro reminders yet." if not items else "Open Sidro reminders:\n" + "\n".join(f"- #{item['id']} {item['title']}" for item in items)
        return _chat_response(conversation_id, reply, [{"tool": "list_reminders", "status": "done", "detail": {"count": len(items)}}])
    if lower.startswith(("create note", "make a note", "save note")):
        title, content = _parse_note(message)
        if not content:
            content = title
            title = "Chat note"
        note = notes.create_note(title, content)
        output = {"note_id": note["id"], "title": note["title"]}
        log_tool("create_note", {"title": title, "content": content}, output)
        return _chat_response(
            conversation_id,
            f"Created note: {note['title']}",
            [{"tool": "create_note", "status": "created", "detail": output}],
        )

    if "list notes" in lower:
        items = notes.list_notes(limit=10)
        log_tool("list_notes", {}, {"count": len(items)})
        if not items:
            reply = "You do not have any notes yet."
        else:
            reply = "Recent notes:\n" + "\n".join(f"- {item['title']}: {item['content'][:120]}" for item in items)
        return _chat_response(conversation_id, reply, [{"tool": "list_notes", "status": "done", "detail": {"count": len(items)}}])

    if lower.startswith("search notes for "):
        query = message[17:].strip()
        items = notes.search_notes(query)
        log_tool("search_notes", {"query": query}, {"count": len(items)})
        reply = "No matching notes found." if not items else "Matching notes:\n" + "\n".join(
            f"- {item['title']}: {item['content'][:140]}" for item in items
        )
        return _chat_response(conversation_id, reply, [{"tool": "search_notes", "status": "done", "detail": {"count": len(items)}}])

    if "current date" in lower or "current time" in lower or lower in {"date", "time", "what time is it"}:
        now = utc_now()
        log_tool("get_current_datetime", {}, {"utc": now})
        return _chat_response(
            conversation_id,
            f"The current server time is {now}.",
            [{"tool": "get_current_datetime", "status": "done", "detail": {"utc": now}}],
        )

    if lower.startswith("search indexed files for "):
        query = message[25:].strip()
        hits = files.search_files(query)
        log_tool("search_indexed_files", {"query": query}, {"count": len(hits)})
        if not hits:
            reply = "I did not find matching indexed file context."
        else:
            reply = "Using file context, I found:\n" + "\n".join(
                f"- {hit['filename']} chunk {hit['chunk_index']}: {hit['content'][:180]}" for hit in hits[:5]
            )
        return _chat_response(
            conversation_id,
            reply,
            [{"tool": "search_indexed_files", "status": "done", "detail": {"count": len(hits)}}],
            used_file_context=bool(hits),
        )

    if lower.startswith("summarize uploaded file"):
        file_id = files.latest_file_id()
        if file_id is None:
            return _chat_response(conversation_id, "Upload a file first, then I can summarize it.")
        chunks = files.get_file_chunks(file_id, limit=12)
        context = "\n\n".join(chunk["content"] for chunk in chunks)
        log_tool("summarize_uploaded_file", {"file_id": file_id}, {"chunks": len(chunks)})
        try:
            summary = ai.complete_chat(
                [
                    {"role": "system", "content": SIDRO_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize this uploaded file clearly and briefly:\n\n{context}"},
                ]
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        filename = chunks[0]["filename"] if chunks else "the uploaded file"
        return _chat_response(
            conversation_id,
            f"Using file context from {filename}: {summary}",
            [{"tool": "summarize_uploaded_file", "status": "done", "detail": {"file_id": file_id}}],
            used_file_context=True,
        )

    if lower.startswith("open website") or lower.startswith("open "):
        action = _open_url_action(message)
        if action:
            log_tool("open_website", {"url": action["url"]}, {"requires_confirmation": True}, status="pending_confirmation")
            return _chat_response(
                conversation_id,
                f"I can open {action['url']} in your browser. Use the Open site action to confirm.",
                [{"tool": "open_website", "status": "awaiting confirmation", "detail": {"url": action["url"]}}],
                [action],
            )

    return None


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    conversation_id = request.conversation_id or _create_conversation(message)
    _save_message(conversation_id, "user", message)

    local = _handle_local_tool(message, conversation_id)
    if local:
        return local

    if quality.is_capability_question(message):
        return _chat_response(
            conversation_id,
            quality.capability_response(message),
            [{"tool": "assistant_quality", "status": "direct", "detail": "Answered from live v1 capabilities"}],
        )

    if quality.is_unsupported_action_request(message):
        return _chat_response(
            conversation_id,
            quality.unsupported_action_response(message),
            [{"tool": "assistant_quality", "status": "blocked", "detail": "Unsupported v1 action request"}],
        )

    prompt_messages: list[dict[str, str]] = [{"role": "system", "content": SIDRO_SYSTEM_PROMPT}]

    remembered = memory.search_memories(message) if request.memory_enabled else []
    if remembered:
        prompt_messages.append(
            {"role": "system", "content": "Useful saved memories:\n" + "\n".join(f"- {item['content']}" for item in remembered)}
        )

    file_hits = files.search_files(message, limit=5) if request.use_file_context else []
    context_summary = _context_summary(remembered, file_hits)

    if file_hits:
        citation_by_chunk = {item["chunk_id"]: item["citation"] for item in context_summary["files"]}
        file_context = "\n\n".join(
            f"Source [{citation_by_chunk.get(hit['chunk_id'], 'F?')}] File: {hit['filename']} / chunk {hit['chunk_index']}\n{hit['content']}"
            for hit in file_hits
        )
        prompt_messages.append(
            {
                "role": "system",
                "content": "You are using indexed file context. Mention that you are using file context in the answer. Cite file-backed claims with bracket labels like [F1].\n\n"
                + file_context,
            }
        )

    prompt_messages.extend(_recent_messages(conversation_id, limit=4))
    style_guidance = quality.answer_style_guidance(message)
    if style_guidance:
        prompt_messages.append({"role": "system", "content": style_guidance})
    prompt_messages.append(
        {
            "role": "system",
            "content": quality.final_response_rules(),
        }
    )

    try:
        reply = ai.complete_chat(prompt_messages)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI request failed: {exc}") from exc

    reply, quality_activities = quality.polish_reply(reply)

    used_file_context = bool(file_hits)
    if used_file_context and "file context" not in reply.lower():
        reply = f"Using file context, {reply}"
    if used_file_context:
        reply = _append_file_sources(reply, context_summary)

    used_memory_context = bool(remembered)
    tool_activities = quality_activities
    if used_memory_context:
        tool_activities.append({"tool": "memory_context", "status": "used", "detail": {"count": len(remembered)}})
        log_tool("search_memories", {"query": message}, {"count": len(remembered)})
    if used_file_context:
        tool_activities.append({"tool": "search_indexed_files", "status": "used", "detail": {"count": len(file_hits)}})
        log_tool("search_indexed_files", {"query": message}, {"count": len(file_hits)})

    suggestion = memory.suggest_from_message(message) if request.memory_enabled else None
    if suggestion:
        tool_activities.append({"tool": "memory_suggestion", "status": "pending", "detail": {"suggestion_id": suggestion["id"], "content": suggestion["content"]}})
        log_tool("memory_suggestion", {"message": message}, {"suggestion_id": suggestion["id"]}, status="pending")

    return _chat_response(
        conversation_id,
        reply,
        tool_activities,
        used_file_context=used_file_context,
        used_memory_context=used_memory_context,
        context_summary=context_summary,
    )


@app.post("/api/context/preview")
def context_preview(request: ContextPreviewRequest) -> dict:
    remembered = memory.search_memories(request.query) if request.memory_enabled else []
    file_hits = files.search_files(request.query, limit=5) if request.use_file_context else []
    summary = _context_summary(remembered, file_hits)
    log_tool(
        "context_preview",
        {"query": request.query, "memory_enabled": request.memory_enabled, "use_file_context": request.use_file_context},
        {"memory_count": summary["memory_count"], "file_count": summary["file_count"]},
    )
    return summary


def _matched_snippet(text: str, query: str, radius: int = 70) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    lower = cleaned.lower()
    needle = query.lower()
    index = lower.find(needle)
    if index < 0:
        return cleaned[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(cleaned), index + len(query) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(cleaned) else ""
    return f"{prefix}{cleaned[start:end].strip()}{suffix}"


@app.get("/api/conversations")
def list_conversations(limit: int = 20, query: str | None = None) -> list[dict]:
    safe_limit = max(1, min(limit, 50))
    search = re.sub(r"\s+", " ", (query or "").strip())
    with get_connection() as conn:
        if search:
            like = f"%{search.lower()}%"
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(all_messages.id) AS message_count,
                    (
                        SELECT m2.content FROM messages m2
                        WHERE m2.conversation_id = c.id AND lower(m2.content) LIKE ?
                        ORDER BY m2.id DESC
                        LIMIT 1
                    ) AS matched_message
                FROM conversations c
                LEFT JOIN messages all_messages ON all_messages.conversation_id = c.id
                WHERE lower(c.title) LIKE ?
                   OR EXISTS (
                       SELECT 1 FROM messages search_messages
                       WHERE search_messages.conversation_id = c.id
                         AND lower(search_messages.content) LIKE ?
                   )
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (like, like, like, safe_limit),
            ).fetchall()
            conversations = []
            for row in rows:
                item = dict(row)
                matched_message = item.pop("matched_message", "") or item["title"]
                item["matched_snippet"] = _matched_snippet(matched_message, search)
                conversations.append(item)
            return conversations

        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) AS message_count,
                   NULL AS matched_snippet
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.patch("/api/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, request: ConversationTitleRequest) -> dict:
    title = re.sub(r"\s+", " ", request.title.strip())[:120]
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, utc_now(), conversation_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return dict(row)


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"deleted": True}


@app.get("/api/conversations/latest")
def latest_conversation() -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 1").fetchone()
    return dict(row) if row else {}


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str) -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, role, content, metadata, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    return {
        "conversation_id": conversation_id,
        "messages": [
            {**dict(row), "metadata": json.loads(row["metadata"] or "{}")}
            for row in rows
        ],
    }


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    suffix = Path(audio.filename or "").suffix.lower()
    if not suffix:
        content_type = (audio.content_type or "").split(";", 1)[0].lower()
        suffix = {
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/mp4": ".m4a",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
        }.get(content_type, ".webm")
    target = DATA_DIR / "audio" / f"{uuid.uuid4().hex}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    audio_bytes = await audio.read()
    if len(audio_bytes) < 512:
        raise HTTPException(status_code=400, detail="Recording was empty or too short. Please hold the mic for a little longer.")
    target.write_bytes(audio_bytes)
    try:
        result = voice.transcribe_audio(target)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc
    return result


@app.post("/api/speak")
def speak(request: SpeakRequest) -> Response:
    try:
        audio_bytes, media_type = voice.synthesize_speech(request.text, request.voice, request.language)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TTS failed: {exc}") from exc
    return Response(content=audio_bytes, media_type=media_type)


@app.get("/api/memories")
def get_memories(category: str | None = None, include_private: bool = True) -> list[dict]:
    return memory.list_memories(category=category, include_private=include_private)


@app.post("/api/memories")
def add_memory(request: MemoryRequest) -> dict:
    item = memory.create_memory(request.content, category=request.category, sensitivity=request.sensitivity, pinned=request.pinned)
    log_tool("create_memory", {"content": request.content, "category": item.get("category")}, {"memory_id": item["id"]})
    return item


@app.patch("/api/memories/{memory_id}")
def update_memory(memory_id: int, request: MemoryUpdateRequest) -> dict:
    try:
        item = memory.update_memory(memory_id, request.content, request.category, request.sensitivity, request.pinned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    log_tool("update_memory", {"memory_id": memory_id}, {"category": item.get("category"), "pinned": item.get("pinned")})
    return item


@app.delete("/api/memories/{memory_id}")
def remove_memory(memory_id: int) -> dict:
    deleted = memory.delete_memory(memory_id)
    log_tool("delete_memory", {"memory_id": memory_id}, {"deleted": deleted})
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": True}


@app.post("/api/memories/merge")
def merge_memories(request: MemoryMergeRequest) -> dict:
    try:
        item = memory.merge_memories(request.memory_ids, request.content, request.category, request.sensitivity, request.pinned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_tool("merge_memories", {"memory_ids": request.memory_ids}, {"memory_id": item["id"]})
    return item


@app.post("/api/memories/similar")
def similar_memories(request: SearchRequest) -> list[dict]:
    return memory.find_similar_memories(request.query)


@app.get("/api/memory-suggestions")
def get_memory_suggestions(status: str = "pending") -> list[dict]:
    return memory.list_suggestions(status=status)


@app.post("/api/memory-suggestions")
def add_memory_suggestion(request: MemorySuggestionRequest) -> dict:
    item = memory.create_suggestion(request.content, request.reason, request.category)
    log_tool("memory_suggestion", {"content": request.content}, {"suggestion_id": item["id"]}, status="pending")
    return item


@app.post("/api/memory-suggestions/{suggestion_id}/accept")
def accept_memory_suggestion(suggestion_id: int, request: MemorySuggestionAcceptRequest) -> dict:
    result = memory.accept_suggestion(suggestion_id, request.pinned, request.sensitivity)
    if result is None:
        raise HTTPException(status_code=404, detail="Memory suggestion not found.")
    log_tool("accept_memory_suggestion", {"suggestion_id": suggestion_id}, {"memory_id": result["memory"]["id"]})
    return result


@app.post("/api/memory-suggestions/{suggestion_id}/dismiss")
def dismiss_memory_suggestion(suggestion_id: int) -> dict:
    item = memory.dismiss_suggestion(suggestion_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory suggestion not found.")
    log_tool("dismiss_memory_suggestion", {"suggestion_id": suggestion_id}, {"status": item["status"]})
    return item


@app.get("/api/today")
def get_today() -> dict:
    return productivity.today_summary()


@app.get("/api/tasks")
def get_tasks(status: str | None = None) -> list[dict]:
    return productivity.list_tasks(status=status)


@app.post("/api/tasks")
def add_task(request: TaskRequest) -> dict:
    task = productivity.create_task(request.title, request.details, request.due_date)
    log_tool("create_task", {"title": request.title}, {"task_id": task["id"]})
    return task


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, request: TaskUpdateRequest) -> dict:
    if request.status is not None and request.status not in {"open", "done"}:
        raise HTTPException(status_code=400, detail="Task status must be open or done.")
    task = productivity.update_task(task_id, request.status, request.title, request.details, request.due_date)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    log_tool("update_task", {"task_id": task_id}, {"status": task.get("status")})
    return task


@app.delete("/api/tasks/{task_id}")
def remove_task(task_id: int) -> dict:
    deleted = productivity.delete_task(task_id)
    log_tool("delete_task", {"task_id": task_id}, {"deleted": deleted})
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"deleted": True}


@app.get("/api/reminders")
def get_reminders(status: str | None = None) -> list[dict]:
    return productivity.list_reminders(status=status)


@app.post("/api/reminders")
def add_reminder(request: ReminderRequest) -> dict:
    reminder = productivity.create_reminder(request.title, request.remind_at)
    log_tool("create_reminder", {"title": request.title}, {"reminder_id": reminder["id"]})
    return reminder


@app.patch("/api/reminders/{reminder_id}")
def update_reminder(reminder_id: int, request: ReminderUpdateRequest) -> dict:
    if request.status is not None and request.status not in {"open", "done"}:
        raise HTTPException(status_code=400, detail="Reminder status must be open or done.")
    reminder = productivity.update_reminder(reminder_id, request.status, request.title, request.remind_at)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    log_tool("update_reminder", {"reminder_id": reminder_id}, {"status": reminder.get("status")})
    return reminder


@app.delete("/api/reminders/{reminder_id}")
def remove_reminder(reminder_id: int) -> dict:
    deleted = productivity.delete_reminder(reminder_id)
    log_tool("delete_reminder", {"reminder_id": reminder_id}, {"deleted": deleted})
    if not deleted:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return {"deleted": True}


@app.post("/api/local-actions/create-file")
def create_local_file(request: LocalFileRequest) -> dict:
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", request.filename).strip(" .")
    if not safe_name:
        raise HTTPException(status_code=400, detail="Filename is required.")
    target_dir = DATA_DIR / "generated"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / safe_name).resolve()
    if target_dir.resolve() not in target.parents:
        raise HTTPException(status_code=400, detail="File must stay inside Sidro generated files.")
    if not request.confirmed:
        log_tool("create_local_file", {"filename": safe_name}, {"requires_confirmation": True}, status="pending_confirmation")
        return {"requires_confirmation": True, "filename": safe_name, "path": str(target)}
    target.write_text(request.content, encoding="utf-8")
    log_tool("create_local_file", {"filename": safe_name}, {"path": str(target)}, status="created")
    return {"created": True, "filename": safe_name, "path": str(target)}

@app.get("/api/notes")
def get_notes() -> list[dict]:
    return notes.list_notes()


@app.post("/api/notes")
def add_note(request: NoteRequest) -> dict:
    item = notes.create_note(request.title, request.content)
    log_tool("create_note", {"title": request.title}, {"note_id": item["id"]})
    return item


@app.post("/api/notes/search")
def search_notes(request: SearchRequest) -> list[dict]:
    hits = notes.search_notes(request.query)
    log_tool("search_notes", {"query": request.query}, {"count": len(hits)})
    return hits


@app.get("/api/files")
def get_files() -> list[dict]:
    return files.list_files()


@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
    try:
        result = await files.index_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_tool("index_file", {"filename": result["filename"]}, {"file_id": result["id"], "chunks": result["chunk_count"]})
    return result


@app.post("/api/files/search")
def search_files(request: SearchRequest) -> list[dict]:
    hits = files.search_files(request.query)
    log_tool("search_indexed_files", {"query": request.query}, {"count": len(hits)})
    return hits


@app.get("/api/tool-logs")
def tool_logs() -> list[dict]:
    return list_tool_logs()


