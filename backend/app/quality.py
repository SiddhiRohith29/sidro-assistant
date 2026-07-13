import re

LIVE_CAPABILITIES = [
    "Chat with Sidro for planning, learning, coding help, writing, and decisions.",
    "Save and search memories that you explicitly ask Sidro to remember.",
    "Create, list, and search local notes in SQLite.",
    "Create and manage local tasks and internal Sidro reminders.",
    "Upload and search indexed text, Markdown, PDF, and DOCX files.",
    "Use indexed file context in chat answers when Files is enabled.",
    "Transcribe English voice input with faster-whisper.",
    "Play voice replies through configured backend TTS or browser speech fallback.",
    "Suggest safe website-open actions that require user confirmation.",
]

UNSUPPORTED_ACTIONS = [
    "direct external calendar scheduling",
    "system-level reminders outside Sidro",
    "moving or renaming local files",
    "sending email",
    "running shell commands",
    "controlling external apps",
]

_UNSUPPORTED_PATTERNS = [
    r"\b(can|will|able to)\s+(add|schedule|create)\b[^.\n]*(calendar|reminder|appointment|meeting)",
    r"\b(can|will|able to)\s+(move|rename|delete|organize)\b[^.\n]*(file|folder|document)",
    r"\b(can|will|able to)\s+(send|draft and send)\b[^.\n]*(email|message)",
    r"\b(can|will|able to)\s+(run|execute)\b[^.\n]*(command|script|program)",
    r"\b(can|will|able to)\s+(control|operate|automate)\b[^.\n]*(app|application|browser|system)",
    r"\bwill remind you\b",
]


def is_capability_question(message: str) -> bool:
    lower = message.lower().strip()
    capability_phrases = [
        "what can you do",
        "what can sidro do",
        "how can sidro help",
        "how can you help",
        "ways sidro can help",
        "ways you can help",
        "help me stay organized",
        "help me organize",
        "what are your capabilities",
        "list your capabilities",
    ]
    return any(phrase in lower for phrase in capability_phrases)


def is_unsupported_action_request(message: str) -> bool:
    lower = message.lower().strip()
    patterns = [
        r"\b(schedule|add|set)\b.*\b(calendar|reminder|appointment|meeting)\b",
        r"\b(remind me|set a reminder)\b",
        r"\b(move|rename|delete|organize)\b.*\b(file|folder|document)\b",
        r"\b(send|reply to)\b.*\b(email|message)\b",
        r"\b(run|execute)\b.*\b(command|script|program|powershell|terminal)\b",
        r"\b(control|automate)\b.*\b(app|application|browser|system)\b",
    ]
    return any(re.search(pattern, lower) for pattern in patterns)


def unsupported_action_response(message: str) -> str:
    return (
        "I cannot perform that action directly in Sidro v1 yet. "
        "I can still help safely by drafting the exact plan, checklist, note, message, command explanation, or manual steps for you to review and apply.\n\n"
        "For example, I can:\n"
        "- create an internal Sidro reminder, or draft an external calendar entry for you to copy;\n"
        "- create a Sidro note with the task details;\n"
        "- outline file organization steps without moving files myself;\n"
        "- write an email draft without sending it;\n"
        "- explain a command without running it.\n\n"
        "Tell me what outcome you want, and I will turn it into a clear manual checklist or note."
    )

def capability_response(message: str) -> str:
    lower = message.lower()
    if "organized" in lower or "organize" in lower:
        return (
            "Here are exactly 3 practical ways Sidro can help you stay organized right now:\n\n"
            "1. **Daily plans and task lists**: Sidro can turn messy thoughts into a clear plan, checklist, or priority list. It cannot schedule an external calendar automatically yet, but it can create local Sidro tasks and internal Sidro reminders.\n\n"
            "2. **Notes and memory**: Sidro can create searchable notes and remember useful preferences when you ask it to. This helps keep recurring details, decisions, and project context from getting lost.\n\n"
            "3. **File and document lookup**: Sidro can index uploaded files, search them, and answer using file context when Files is enabled. This is useful for finding details inside notes, PDFs, docs, or project material without manually scanning everything.\n\n"
            "Best next step: use Sidro for one daily plan, one note, and one uploaded document so the system starts working around your real routine."
        )

    capabilities = "\n".join(f"- {item}" for item in LIVE_CAPABILITIES)
    unsupported = ", ".join(UNSUPPORTED_ACTIONS)
    return (
        "Sidro v1 can do these things right now:\n"
        f"{capabilities}\n\n"
        f"Not yet live in v1: {unsupported}. For those, I can draft plans, checklists, notes, or step-by-step instructions for you to apply manually."
    )


def answer_style_guidance(message: str) -> str:
    lower = message.lower().strip()
    guidance: list[str] = []

    if any(word in lower for word in ["summarize", "summary", "recap", "brief me"]):
        guidance.append(
            "For this summary request: start with a one-sentence gist, then 3-6 concrete bullets, then a short final takeaway. Do not omit important caveats."
        )

    if any(word in lower for word in ["compare", "comparison", "versus", " vs ", "difference", "better"]):
        guidance.append(
            "For this comparison request: identify the options, compare them across practical criteria, name the best default choice, and mention when another option wins."
        )

    if any(word in lower for word in ["extract", "find", "from the document", "from this file", "what does the file", "according to"]):
        guidance.append(
            "For this extraction or document question: answer only from available context when context is provided, include exact details, and cite file labels like [F1] for file-backed claims."
        )

    if any(word in lower for word in ["plan", "roadmap", "phase", "steps", "checklist"]):
        guidance.append(
            "For this planning request: organize the response into clear steps or phases, include acceptance checks, and call out the next action."
        )

    if re.search(r"\btop\s+\d+\b|\bexactly\s+\d+\b|\b\d+\s+(ideas|options|ways|brands|items|examples)\b", lower):
        guidance.append(
            "For this counted-list request: provide exactly the requested number of items, number them clearly, and make every item complete enough to stand alone."
        )

    if not guidance:
        return ""
    return "Phase 6 answer-shape guidance:\n" + "\n".join(f"- {item}" for item in guidance)

def final_response_rules() -> str:
    return (
        "Final response rules: finish the answer fully; satisfy the exact count requested by the user; "
        "prefer concise paragraphs or 3-7 concrete bullets unless the user asks for more; "
        "include examples only when they make the answer actionable; state assumptions; avoid filler; "
        "do not trail off; avoid repeating the same idea; avoid duplicate schedule blocks; "
        "if there are tradeoffs, name the best recommendation; end with a useful final sentence. "
        "Hard capability boundary: Sidro v1 can actually do these things now: chat, save/search memories, create/search notes, create/manage local tasks and internal Sidro reminders, upload/search indexed files, transcribe English voice input, play voice replies through backend TTS or browser fallback, and suggest safe website-open actions. "
        "Do not say or imply that Sidro can directly schedule calendars, move/rename local files, send email, run shell commands, control apps, or create reminders automatically. "
        "For unsupported actions, say Sidro can draft a plan, checklist, note, or instructions that Siddharth can apply manually."
    )


def polish_reply(reply: str) -> tuple[str, list[dict]]:
    cleaned = re.sub(r"^(certainly|sure|of course)[!,.]?\s*", "", reply.strip(), flags=re.I)
    activities: list[dict] = []
    lower = cleaned.lower()
    if any(re.search(pattern, lower, flags=re.I) for pattern in _UNSUPPORTED_PATTERNS):
        note = (
            "\n\nV1 boundary: I can help draft plans, checklists, notes, and instructions for calendar/reminder/file/email/app tasks, "
            "but I do not perform those external actions directly yet."
        )
        if "v1 boundary" not in lower:
            cleaned = f"{cleaned}{note}"
        activities.append({"tool": "assistant_quality", "status": "capability boundary added", "detail": "Unsupported action wording detected"})
    return cleaned, activities