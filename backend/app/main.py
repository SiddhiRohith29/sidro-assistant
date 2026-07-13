import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import ai, files, memory, notes, quality, voice
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


class NoteRequest(BaseModel):
    title: str = "Untitled note"
    content: str = Field(min_length=1)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


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
        "quality_phase": 2,
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
    }


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


def _chat_response(
    conversation_id: str,
    reply: str,
    tool_activities: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    used_file_context: bool = False,
) -> dict:
    _save_message(
        conversation_id,
        "assistant",
        reply,
        {"tool_activities": tool_activities or [], "actions": actions or [], "used_file_context": used_file_context},
    )
    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "language": detect_language(reply),
        "tool_activities": tool_activities or [],
        "actions": actions or [],
        "used_file_context": used_file_context,
    }


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
    if file_hits:
        file_context = "\n\n".join(
            f"File: {hit['filename']} / chunk {hit['chunk_index']}\n{hit['content']}" for hit in file_hits
        )
        prompt_messages.append(
            {
                "role": "system",
                "content": "You are using indexed file context. Mention that you are using file context in the answer.\n\n"
                + file_context,
            }
        )

    prompt_messages.extend(_recent_messages(conversation_id, limit=4))
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

    tool_activities = quality_activities
    if used_file_context:
        tool_activities.append({"tool": "search_indexed_files", "status": "used", "detail": {"count": len(file_hits)}})
        log_tool("search_indexed_files", {"query": message}, {"count": len(file_hits)})

    return _chat_response(conversation_id, reply, tool_activities, used_file_context=used_file_context)


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
def get_memories() -> list[dict]:
    return memory.list_memories()


@app.post("/api/memories")
def add_memory(request: MemoryRequest) -> dict:
    item = memory.create_memory(request.content)
    log_tool("create_memory", {"content": request.content}, {"memory_id": item["id"]})
    return item


@app.delete("/api/memories/{memory_id}")
def remove_memory(memory_id: int) -> dict:
    deleted = memory.delete_memory(memory_id)
    log_tool("delete_memory", {"memory_id": memory_id}, {"deleted": deleted})
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": True}


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

