from __future__ import annotations

ENGLISH = "en"
UNKNOWN = "unknown"


def contains_latin(text: str) -> bool:
    return any("a" <= char.lower() <= "z" for char in text)


def detect_language(text: str) -> str:
    clean = text.strip()
    if not clean:
        return UNKNOWN
    has_latin = contains_latin(clean)

    try:
        from langdetect import detect

        detected = detect(clean)
        if detected == ENGLISH:
            return ENGLISH
    except Exception:
        pass

    return ENGLISH if has_latin else UNKNOWN
