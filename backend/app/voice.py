from __future__ import annotations

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from . import ai
from .config import get_settings
from .language import detect_language


@lru_cache(maxsize=4)
def _whisper_model(model_name: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_audio(path: Path) -> dict:
    settings = get_settings()
    provider = settings.stt_provider
    if provider not in {"auto", "openai", "faster_whisper"}:
        raise RuntimeError("SIDRO_STT_PROVIDER must be auto, openai, or faster_whisper.")

    if provider == "faster_whisper":
        return _transcribe_faster_whisper(path)
    if provider == "openai":
        text = ai.transcribe_audio(path)
        return {"text": text, "language": detect_language(text), "provider": "openai"}

    try:
        return _transcribe_faster_whisper(path)
    except Exception:
        if not settings.openai_api_key:
            raise
        text = ai.transcribe_audio(path)
        return {"text": text, "language": detect_language(text), "provider": "openai"}


def _transcribe_faster_whisper(path: Path) -> dict:
    settings = get_settings()
    try:
        model = _whisper_model(
            settings.faster_whisper_model,
            settings.faster_whisper_device,
            settings.faster_whisper_compute_type,
        )
    except ImportError as exc:
        raise RuntimeError(f"faster-whisper could not start: {exc}. Run `pip install -r requirements.txt`.") from exc

    segments, info = model.transcribe(str(path), language="en", vad_filter=True)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    language = getattr(info, "language", None) or detect_language(text)
    return {"text": text, "language": language, "provider": "faster_whisper"}


def synthesize_speech(text: str, voice: str | None = None, language: str | None = None) -> tuple[bytes, str]:
    settings = get_settings()
    provider = settings.tts_provider

    if provider not in {"auto", "openai", "piper", "command"}:
        raise RuntimeError("SIDRO_TTS_PROVIDER must be auto, openai, piper, or command.")

    if provider == "command":
        raise RuntimeError("Command TTS is not configured in the simplified local setup.")
    if provider == "piper" or (provider == "auto" and settings.piper_exe and settings.piper_model):
        return _speak_piper(text), "audio/wav"
    if provider == "openai" or provider == "auto":
        return ai.synthesize_speech(text, voice), "audio/mpeg"

    raise RuntimeError("No TTS provider is configured.")


def _speak_piper(text: str) -> bytes:
    settings = get_settings()
    piper_exe = settings.piper_exe
    model_path = settings.piper_model
    if not piper_exe or not model_path:
        raise RuntimeError("PIPER_EXE and PIPER_MODEL must be configured for Piper TTS.")

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "sidro-tts.wav"
        result = subprocess.run(
            [piper_exe, "--model", model_path, "--output_file", str(output_path)],
            input=text,
            text=True,
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper TTS failed: {result.stderr.strip() or result.stdout.strip()}")
        return output_path.read_bytes()


def _speak_command(text: str, command_template: str) -> bytes:
    with tempfile.TemporaryDirectory() as temp_dir:
        text_path = Path(temp_dir) / "input.txt"
        output_path = Path(temp_dir) / "output.wav"
        text_path.write_text(text, encoding="utf-8")
        command = command_template.format(text_file=str(text_path), output_file=str(output_path), text=text)
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError(f"Local TTS command failed: {result.stderr.strip() or result.stdout.strip()}")
        if not output_path.exists():
            raise RuntimeError("Local TTS command did not create the expected output file.")
        return output_path.read_bytes()
