import os
import sys
from pathlib import Path

import requests

BASE_URL = os.getenv("SIDRO_BACKEND_URL", "http://127.0.0.1:8021").rstrip("/")


def ok(label: str, detail: str = "") -> None:
    print(f"[OK] {label}{': ' + detail if detail else ''}")


def fail(label: str, detail: str) -> None:
    print(f"[FAIL] {label}: {detail}")
    raise SystemExit(1)


def request(method: str, path: str, **kwargs):
    try:
        response = requests.request(method, f"{BASE_URL}{path}", timeout=45, **kwargs)
    except requests.RequestException as exc:
        fail(path, str(exc))
    return response


def expect_success(label: str, response):
    if not response.ok:
        fail(label, f"HTTP {response.status_code} {response.text[:300]}")
    ok(label)
    return response.json() if response.content else {}


def main() -> None:
    print(f"Sidro v1 verification against {BASE_URL}")

    health = expect_success("Backend health", request("GET", "/api/health"))
    if not health.get("ok"):
        fail("Backend health", "health response did not report ok=true")
    if health.get("quality_phase", 0) < 4:
        fail("Phase 4 health marker", "backend did not report quality_phase >= 4")
    ok("Phase 4 health marker", f"quality_phase={health.get('quality_phase')}")

    settings = expect_success("Settings endpoint", request("GET", "/api/settings"))
    ok("Settings loaded", f"provider={settings.get('chat_provider')} ollama={settings.get('ollama_model')}")

    memory_payload = {
        "message": "remember that Sidro v1 verification checks should stay reliable",
        "use_file_context": False,
        "memory_enabled": True,
    }
    chat_memory = expect_success("Chat local memory tool", request("POST", "/api/chat", json=memory_payload))
    if "Remembered" not in chat_memory.get("reply", ""):
        fail("Chat local memory tool", "memory tool did not return confirmation")

    duplicate_memory = "Sidro phase 3 duplicate guard remembers coral compass"
    first_memory = expect_success("Create Phase 3 memory", request("POST", "/api/memories", json={"content": duplicate_memory}))
    second_memory = expect_success("Duplicate memory guard", request("POST", "/api/memories", json={"content": duplicate_memory}))
    if first_memory.get("id") != second_memory.get("id"):
        fail("Duplicate memory guard", "same memory text created a duplicate record")
    capability = expect_success(
        "Phase 2 capability boundary",
        request(
            "POST",
            "/api/chat",
            json={
                "message": "Give me exactly 3 practical ways Sidro can help me stay organized.",
                "use_file_context": False,
                "memory_enabled": False,
            },
        ),
    )
    capability_reply = capability.get("reply", "").lower()
    if "exactly 3" not in capability_reply or "cannot schedule" not in capability_reply:
        fail("Phase 2 capability boundary", "capability response did not clearly state v1 limits")
    if "add this to your calendar" in capability_reply or "will remind you" in capability_reply:
        fail("Phase 2 capability boundary", "capability response overpromised unsupported calendar/reminder actions")
    unsupported = expect_success(
        "Phase 2 unsupported action guard",
        request(
            "POST",
            "/api/chat",
            json={
                "message": "Schedule a reminder for tomorrow morning to review Sidro.",
                "use_file_context": False,
                "memory_enabled": False,
            },
        ),
    )
    unsupported_reply = unsupported.get("reply", "").lower()
    if "cannot perform that action directly" not in unsupported_reply or "manual checklist" not in unsupported_reply:
        fail("Phase 2 unsupported action guard", "unsupported action response was not direct or safe")
    if "scheduled" in unsupported_reply or "i will remind" in unsupported_reply:
        fail("Phase 2 unsupported action guard", "unsupported action response claimed the action was performed")

    note = expect_success(
        "Create note",
        request("POST", "/api/notes", json={"title": "Sidro v1 verification", "content": "Notes search should find the nebula keyword."}),
    )
    if not note.get("id"):
        fail("Create note", "note id missing")

    note_hits = expect_success("Search notes", request("POST", "/api/notes/search", json={"query": "nebula"}))
    if not any("nebula" in item.get("content", "").lower() for item in note_hits):
        fail("Search notes", "created note was not found")

    sample_text = (
        "Sidro verification sample file. The keyword starforge proves indexed file search works. "
        "This file is safe test content for the v1 acceptance script."
    )
    files = {"file": ("sidro-v1-sample.txt", sample_text.encode("utf-8"), "text/plain")}
    uploaded = expect_success("Upload text file", request("POST", "/api/files/upload", files=files))
    if uploaded.get("chunk_count", 0) < 1:
        fail("Upload text file", "file did not create chunks")

    file_hits = expect_success("Search indexed files", request("POST", "/api/files/search", json={"query": "starforge"}))
    if not any("starforge" in item.get("content", "").lower() for item in file_hits):
        fail("Search indexed files", "uploaded file was not found")

    context_preview = expect_success(
        "Phase 3 context preview",
        request("POST", "/api/context/preview", json={"query": "coral compass starforge", "memory_enabled": True, "use_file_context": True}),
    )
    if context_preview.get("memory_count", 0) < 1:
        fail("Phase 3 context preview", "memory context was not surfaced")
    if context_preview.get("file_count", 0) < 1:
        fail("Phase 3 context preview", "file context was not surfaced")
    if not all(item.get("citation") for item in context_preview.get("files", [])):
        fail("Phase 4 source labels", "file context did not include citation labels")
    ok("Phase 3 context counts", f"memory={context_preview.get('memory_count')} files={context_preview.get('file_count')}")
    ok("Phase 4 source labels", ", ".join(item.get("citation", "") for item in context_preview.get("files", [])[:3]))

    short_audio = request(
        "POST",
        "/api/transcribe",
        files={"audio": ("too-short.webm", b"x", "audio/webm")},
    )
    if short_audio.status_code != 400 or "too short" not in short_audio.text.lower():
        fail("Voice short-recording guard", f"expected helpful 400, got {short_audio.status_code}: {short_audio.text[:200]}")
    ok("Voice short-recording guard")

    tts = request("POST", "/api/speak", json={"text": "Sidro voice check", "voice": settings.get("tts_voice", "alloy")})
    if tts.ok:
        ok("Backend TTS", tts.headers.get("content-type", "audio returned"))
    elif tts.status_code in {400, 502} and "tts" in tts.text.lower():
        ok("TTS fallback path", "backend unavailable; frontend browser voice fallback is expected")
    else:
        fail("TTS fallback path", f"unexpected HTTP {tts.status_code}: {tts.text[:200]}")

    print("Sidro v1 + Phase 4 verification passed.")


if __name__ == "__main__":
    main()