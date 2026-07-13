from pathlib import Path

import httpx
from openai import OpenAI

from .config import get_settings


def get_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in .env.")
    return OpenAI(api_key=settings.openai_api_key)


def complete_chat(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    provider = settings.chat_provider

    if provider not in {"auto", "openai", "ollama"}:
        raise RuntimeError("SIDRO_CHAT_PROVIDER must be auto, openai, or ollama.")

    if provider == "ollama":
        return complete_chat_ollama(messages)

    if provider == "auto" and not settings.openai_api_key:
        return complete_chat_ollama(messages)

    try:
        return complete_chat_openai(messages)
    except Exception as exc:
        if provider == "auto":
            return complete_chat_ollama(messages)
        raise exc


def complete_chat_openai(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    response = get_client().chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=0.35,
    )
    return response.choices[0].message.content or ""


def complete_chat_ollama(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    model = settings.ollama_model
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.22,
            "top_p": 0.9,
            "repeat_penalty": 1.08,
            "num_predict": settings.ollama_num_predict,
            "num_ctx": settings.ollama_num_ctx,
        },
    }
    try:
        response = httpx.post(f"{settings.ollama_base_url.rstrip('/')}/api/chat", json=payload, timeout=240)
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "Ollama is not running. Start it, then run `ollama pull qwen2.5:7b` and try again."
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise RuntimeError(f"Ollama request failed for model `{model}`: {detail}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    data = response.json()
    return data.get("message", {}).get("content", "") or ""


def transcribe_audio(path: Path) -> str:
    settings = get_settings()
    with path.open("rb") as audio_file:
        response = get_client().audio.transcriptions.create(
            model=settings.transcription_model,
            file=audio_file,
        )
    return response.text


def synthesize_speech(text: str, voice: str | None = None) -> bytes:
    settings = get_settings()
    response = get_client().audio.speech.create(
        model=settings.tts_model,
        voice=voice or settings.tts_voice,
        input=text[:4000],
        response_format="mp3",
    )
    if hasattr(response, "read"):
        return response.read()
    return response.content

