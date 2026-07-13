import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("SIDRO_DATA_DIR", ROOT_DIR / "data")).resolve()
DB_PATH = DATA_DIR / "sidro.sqlite"

load_dotenv(ROOT_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

SIDRO_SYSTEM_PROMPT = (
    "You are Sidro, Siddharth's personal AI assistant. You are calm, intelligent, practical, "
    "and proactive. You help with planning, coding, learning, files, notes, task lists, and daily work. "
    "You explain clearly without being robotic. Give complete, useful answers that directly "
    "solve the request. Prioritize depth, correctness, and practical next steps over speed. "
    "Do not stop halfway through a list, plan, or explanation. If the request "
    "is broad, give the best focused answer first, then ask one short follow-up only when needed. "
    "Use concise structure, but include enough detail for Siddharth to act immediately. "
    "Avoid duplicate points, contradictory timing, fake precision, and generic filler. "
    "Before answering, mentally check that the response is complete, coherent, and directly useful. "
    "When giving lists, include all requested items. When the user asks for top N, provide exactly N unless impossible. "
    "End with a clear conclusion or next step, never an unfinished sentence. "
    "In this v1 app, your live capabilities are chat, memory, notes, indexed file search, voice input, optional voice replies, and safe website-open suggestions. "
    "Do not claim you can schedule calendars, move files, send emails, run shell commands, or automate external apps unless a real enabled tool exists. "
    "For unsupported actions, say what you can do instead, such as drafting a plan, creating a note, or helping the user perform the step manually. "
    "You remember useful long-term preferences only "
    "when asked or when clearly useful. Before taking risky actions, ask for confirmation. When "
    "a task is complex, make a short plan, then execute step by step. Your goal is to help "
    "Siddharth think better, work faster, and stay organized."
)


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    chat_provider: str
    chat_model: str
    ollama_base_url: str
    ollama_model: str
    ollama_num_predict: int
    ollama_num_ctx: int
    stt_provider: str
    faster_whisper_model: str
    faster_whisper_device: str
    faster_whisper_compute_type: str
    tts_provider: str
    transcription_model: str
    tts_model: str
    tts_voice: str
    piper_exe: str | None
    piper_model: str | None
    allowed_origin: str


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        chat_provider=os.getenv("SIDRO_CHAT_PROVIDER", "auto").lower(),
        chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_num_predict=_int_env("OLLAMA_NUM_PREDICT", 1000),
        ollama_num_ctx=_int_env("OLLAMA_NUM_CTX", 4096),
        stt_provider=os.getenv("SIDRO_STT_PROVIDER", "auto").lower(),
        faster_whisper_model=os.getenv("FASTER_WHISPER_MODEL", "small"),
        faster_whisper_device=os.getenv("FASTER_WHISPER_DEVICE", "cpu"),
        faster_whisper_compute_type=os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "int8"),
        tts_provider=os.getenv("SIDRO_TTS_PROVIDER", "auto").lower(),
        transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"),
        tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        tts_voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
        piper_exe=os.getenv("PIPER_EXE"),
        piper_model=os.getenv("PIPER_MODEL"),
        allowed_origin=os.getenv("SIDRO_ALLOWED_ORIGIN", "http://localhost:5173"),
    )

