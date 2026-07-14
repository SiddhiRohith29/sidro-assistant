import re
from pathlib import Path

import httpx
from openai import OpenAI

from .config import get_settings


_MODEL_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,80}$")


def get_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in .env.")
    return OpenAI(api_key=settings.openai_api_key)


def _normalize_provider(provider: str) -> str:
    provider = provider.lower().strip()
    if provider == "local":
        return "ollama"
    if provider == "hybrid":
        return "auto"
    return provider


def complete_chat(messages: list[dict[str, str]], provider_override: str | None = None, model_override: str | None = None) -> str:
    settings = get_settings()
    provider = _normalize_provider(provider_override or settings.chat_provider)

    if provider not in {"auto", "openai", "ollama"}:
        raise RuntimeError("Provider must be auto, openai, ollama, local, or hybrid.")

    if provider == "ollama":
        return complete_chat_ollama(messages, model_override)

    if provider == "auto" and not settings.openai_api_key:
        return complete_chat_ollama(messages, model_override)

    try:
        return complete_chat_openai(messages, model_override)
    except Exception as exc:
        if provider == "auto":
            return complete_chat_ollama(messages, model_override)
        raise exc


def complete_chat_openai(messages: list[dict[str, str]], model_override: str | None = None) -> str:
    settings = get_settings()
    response = get_client().chat.completions.create(
        model=model_override or settings.chat_model,
        messages=messages,
        temperature=0.35,
    )
    return response.choices[0].message.content or ""


def complete_chat_ollama(messages: list[dict[str, str]], model_override: str | None = None) -> str:
    settings = get_settings()
    model = model_override or settings.ollama_model
    if not _MODEL_RE.match(model):
        raise RuntimeError("Invalid Ollama model name selected.")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.28,
            "top_p": 0.92,
            "repeat_penalty": 1.06,
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


def list_ollama_models(timeout: float = 2.5) -> list[str]:
    settings = get_settings()
    models: list[str] = []
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        models = [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
    except httpx.HTTPError:
        models = []
    if settings.ollama_model not in models:
        models.insert(0, settings.ollama_model)
    return list(dict.fromkeys(models))


def routing_summary(provider_override: str | None = None, model_override: str | None = None) -> dict:
    settings = get_settings()
    requested = provider_override or settings.chat_provider
    provider = _normalize_provider(requested)
    if provider == "auto" and not settings.openai_api_key:
        active_provider = "ollama"
    elif provider == "auto":
        active_provider = "openai-with-ollama-fallback"
    else:
        active_provider = provider
    default_model = settings.chat_model if active_provider.startswith("openai") else settings.ollama_model
    return {
        "requested_provider": requested,
        "active_provider": active_provider,
        "model": model_override or default_model,
        "openai_configured": bool(settings.openai_api_key),
    }


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
