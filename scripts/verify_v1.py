import os
import sys
from pathlib import Path

import requests

BASE_URL = os.getenv("SIDRO_BACKEND_URL", "http://127.0.0.1:8022").rstrip("/")


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
    if health.get("quality_phase", 0) < 6:
        fail("Phase 6 health marker", "backend did not report quality_phase >= 6")
    ok("Phase 6 health marker", f"quality_phase={health.get('quality_phase')}")
    if health.get("roadmap_complete_phase", 0) < 9:
        fail("Roadmap Phase 1-9 completion marker", "backend did not report roadmap_complete_phase >= 9")
    ok("Roadmap Phase 1-9 completion marker", f"phase={health.get('roadmap_complete_phase')}")

    settings = expect_success("Settings endpoint", request("GET", "/api/settings"))
    ok("Settings loaded", f"provider={settings.get('chat_provider')} ollama={settings.get('ollama_model')}")
    if settings.get("ui_phase", 0) < 8:
        fail("Phase 8 settings marker", "settings did not report ui_phase >= 8")
    shortcuts = settings.get("keyboard_shortcuts") or []
    shortcut_keys = {item.get("keys") for item in shortcuts}
    if not {"Ctrl+K", "Ctrl+N", "Ctrl+B", "Escape"}.issubset(shortcut_keys):
        fail("Phase 8 keyboard shortcuts", "settings did not list the expected keyboard shortcuts")
    accessibility = settings.get("accessibility") or {}
    if not all(accessibility.get(key) for key in ["skip_link", "landmarks", "live_status", "responsive_mobile_nav"]):
        fail("Phase 8 accessibility settings", "accessibility flags were incomplete")
    ok("Phase 8 UI/UX settings", f"shortcuts={len(shortcuts)}")
    if settings.get("reliability_phase", 0) < 9:
        fail("Phase 9 reliability settings", "settings did not report reliability_phase >= 9")
    features = set(settings.get("reliability_features") or [])
    expected_features = {"startup_check", "backup", "restore_preview", "migration_safety", "friendly_errors", "one_click_launcher"}
    if not expected_features.issubset(features):
        fail("Phase 9 reliability settings", "settings did not list the expected reliability features")
    ok("Phase 9 reliability settings", f"features={len(features)}")

    reliability = expect_success("Phase 9 startup health check", request("GET", "/api/reliability/startup-check"))
    if reliability.get("phase", 0) < 9:
        fail("Phase 9 startup health check", "startup report did not report phase >= 9")
    if not reliability.get("ok"):
        fail("Phase 9 startup health check", "startup report had a failed critical check")
    check_names = {item.get("name") for item in reliability.get("checks", [])}
    for required in ["Data folder", "Uploads folder", "Audio folder", "Backups folder", "SQLite database"]:
        if required not in check_names:
            fail("Phase 9 startup health check", f"missing check: {required}")
    ok("Phase 9 startup health details", f"checks={len(check_names)}")

    backup = expect_success("Phase 9 backup create", request("POST", "/api/reliability/backups", json={"label": "verifier"}))
    backup_name = backup.get("filename")
    if not backup_name or not backup_name.endswith(".sqlite"):
        fail("Phase 9 backup create", "backup filename was missing or invalid")
    backups = expect_success("Phase 9 backup list", request("GET", "/api/reliability/backups"))
    if not any(item.get("filename") == backup_name for item in backups):
        fail("Phase 9 backup list", "created backup was not listed")
    restore_preview = expect_success("Phase 9 restore preview", request("POST", "/api/reliability/restore", json={"filename": backup_name, "confirmed": False}))
    if not restore_preview.get("requires_confirmation"):
        fail("Phase 9 restore preview", "restore did not require confirmation")
    validation = request("POST", "/api/reliability/restore", json={})
    if validation.status_code != 422 or "Sidro could not understand" not in validation.text:
        fail("Phase 9 friendly validation error", f"unexpected response: {validation.status_code} {validation.text[:160]}")
    ok("Phase 9 friendly validation error")

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
    phase7_memory = expect_success(
        "Phase 7 memory create metadata",
        request(
            "POST",
            "/api/memories",
            json={
                "content": "Sidro phase 7 remembers that I prefer memory controls with review",
                "category": "preference",
                "sensitivity": "private",
                "pinned": True,
            },
        ),
    )
    phase7_memory_id = phase7_memory.get("id")
    if phase7_memory.get("category") != "preference" or phase7_memory.get("sensitivity") != "private" or not phase7_memory.get("pinned"):
        fail("Phase 7 memory create metadata", "metadata was not saved")
    edited_memory = expect_success(
        "Phase 7 memory edit",
        request(
            "PATCH",
            f"/api/memories/{phase7_memory_id}",
            json={"content": "Sidro phase 7 edited memory preference", "category": "workflow", "sensitivity": "normal", "pinned": False},
        ),
    )
    if edited_memory.get("category") != "workflow" or edited_memory.get("sensitivity") != "normal" or edited_memory.get("pinned"):
        fail("Phase 7 memory edit", "memory edit did not persist metadata")
    similar = expect_success("Phase 7 similar memories", request("POST", "/api/memories/similar", json={"query": "Sidro phase 7 edited memory preference"}))
    if not any(item.get("id") == phase7_memory_id for item in similar):
        fail("Phase 7 similar memories", "similar search did not find edited memory")

    merge_a = expect_success("Phase 7 merge source A", request("POST", "/api/memories", json={"content": "Phase 7 merge source alpha", "category": "project"}))
    merge_b = expect_success("Phase 7 merge source B", request("POST", "/api/memories", json={"content": "Phase 7 merge source beta", "category": "project"}))
    merged = expect_success(
        "Phase 7 memory merge",
        request(
            "POST",
            "/api/memories/merge",
            json={"memory_ids": [merge_a.get("id"), merge_b.get("id")], "content": "Phase 7 merged project memory", "category": "project", "pinned": True},
        ),
    )
    if merged.get("category") != "project" or not merged.get("pinned"):
        fail("Phase 7 memory merge", "merged memory metadata was wrong")

    suggestion = expect_success(
        "Phase 7 memory suggestion create",
        request("POST", "/api/memory-suggestions", json={"content": "I prefer Phase 7 suggestions to require approval", "category": "preference"}),
    )
    suggestions = expect_success("Phase 7 memory suggestion list", request("GET", "/api/memory-suggestions"))
    if not any(item.get("id") == suggestion.get("id") for item in suggestions):
        fail("Phase 7 memory suggestion list", "pending suggestion was not listed")
    accepted = expect_success("Phase 7 memory suggestion accept", request("POST", f"/api/memory-suggestions/{suggestion.get('id')}/accept", json={"pinned": True}))
    if not accepted.get("memory", {}).get("id"):
        fail("Phase 7 memory suggestion accept", "suggestion did not create a memory")
    dismiss = expect_success(
        "Phase 7 memory suggestion dismiss setup",
        request("POST", "/api/memory-suggestions", json={"content": "I prefer Phase 7 dismiss testing", "category": "preference"}),
    )
    dismissed = expect_success("Phase 7 memory suggestion dismiss", request("POST", f"/api/memory-suggestions/{dismiss.get('id')}/dismiss"))
    if dismissed.get("status") != "dismissed":
        fail("Phase 7 memory suggestion dismiss", "suggestion was not dismissed")
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

    workflow_chat = expect_success(
        "Phase 5 conversation create",
        request(
            "POST",
            "/api/chat",
            json={
                "message": "Phase 5 workflow conversation library check",
                "use_file_context": False,
                "memory_enabled": False,
            },
        ),
    )
    workflow_id = workflow_chat.get("conversation_id")
    if not workflow_id:
        fail("Phase 5 conversation create", "conversation id missing")
    conversations = expect_success("Phase 5 conversation list", request("GET", "/api/conversations"))
    if not any(item.get("id") == workflow_id for item in conversations):
        fail("Phase 5 conversation list", "created conversation was not listed")
    messages = expect_success("Phase 5 conversation resume", request("GET", f"/api/conversations/{workflow_id}/messages"))
    if len(messages.get("messages", [])) < 2:
        fail("Phase 5 conversation resume", "created conversation did not return saved messages")
    renamed = expect_success(
        "Phase 5 conversation rename",
        request("PATCH", f"/api/conversations/{workflow_id}", json={"title": "Phase 5 workflow check"}),
    )
    if renamed.get("title") != "Phase 5 workflow check":
        fail("Phase 5 conversation rename", "conversation title did not update")
    deleted = expect_success("Phase 5 conversation delete", request("DELETE", f"/api/conversations/{workflow_id}"))
    if not deleted.get("deleted"):
        fail("Phase 5 conversation delete", "delete response did not confirm deletion")
    phase6_phrase = "Phase 6 searchable conversation aurora-lattice"
    phase6_chat = expect_success(
        "Phase 6 searchable conversation create",
        request(
            "POST",
            "/api/chat",
            json={
                "message": phase6_phrase,
                "use_file_context": False,
                "memory_enabled": False,
            },
        ),
    )
    phase6_id = phase6_chat.get("conversation_id")
    if not phase6_id:
        fail("Phase 6 searchable conversation create", "conversation id missing")
    searched = expect_success("Phase 6 conversation search", request("GET", "/api/conversations", params={"query": "aurora-lattice"}))
    match = next((item for item in searched if item.get("id") == phase6_id), None)
    if not match:
        fail("Phase 6 conversation search", "search did not return the created conversation")
    if "aurora-lattice" not in (match.get("matched_snippet") or "").lower():
        fail("Phase 6 conversation search", "matched snippet did not include the searched text")
    expect_success("Phase 6 conversation cleanup", request("DELETE", f"/api/conversations/{phase6_id}"))
    task = expect_success(
        "Phase 4 task create",
        request("POST", "/api/tasks", json={"title": "Verify Sidro task workflow", "details": "Created by verifier"}),
    )
    task_id = task.get("id")
    if not task_id:
        fail("Phase 4 task create", "task id missing")
    task_list = expect_success("Phase 4 task list", request("GET", "/api/tasks", params={"status": "open"}))
    if not any(item.get("id") == task_id for item in task_list):
        fail("Phase 4 task list", "created task was not listed")
    task_done = expect_success("Phase 4 task complete", request("PATCH", f"/api/tasks/{task_id}", json={"status": "done"}))
    if task_done.get("status") != "done":
        fail("Phase 4 task complete", "task status did not update")

    reminder = expect_success(
        "Phase 4 reminder create",
        request("POST", "/api/reminders", json={"title": "Verify Sidro internal reminder"}),
    )
    reminder_id = reminder.get("id")
    if not reminder_id:
        fail("Phase 4 reminder create", "reminder id missing")
    reminders = expect_success("Phase 4 reminder list", request("GET", "/api/reminders", params={"status": "open"}))
    if not any(item.get("id") == reminder_id for item in reminders):
        fail("Phase 4 reminder list", "created reminder was not listed")
    reminder_done = expect_success("Phase 4 reminder complete", request("PATCH", f"/api/reminders/{reminder_id}", json={"status": "done"}))
    if reminder_done.get("status") != "done":
        fail("Phase 4 reminder complete", "reminder status did not update")

    today = expect_success("Phase 4 Today dashboard", request("GET", "/api/today"))
    if "counts" not in today or "open_tasks" not in today or "open_reminders" not in today:
        fail("Phase 4 Today dashboard", "today summary shape was incomplete")

    preview_file = expect_success(
        "Phase 6 safe file action preview",
        request("POST", "/api/local-actions/create-file", json={"filename": "phase6-action-check.txt", "content": "safe action", "confirmed": False}),
    )
    if not preview_file.get("requires_confirmation"):
        fail("Phase 6 safe file action preview", "file action did not require confirmation")
    created_file = expect_success(
        "Phase 6 safe file action confirmed",
        request("POST", "/api/local-actions/create-file", json={"filename": "phase6-action-check.txt", "content": "safe action", "confirmed": True}),
    )
    if not created_file.get("created"):
        fail("Phase 6 safe file action confirmed", "confirmed file action did not create a file")

    logs = expect_success("Phase 6 tool history", request("GET", "/api/tool-logs"))
    if not any(item.get("tool_name") in {"create_task", "create_reminder", "create_local_file"} for item in logs):
        fail("Phase 6 tool history", "expected tool activity was not logged")

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

    print("Sidro v1 + Phase 9 verification passed.")


if __name__ == "__main__":
    main()
