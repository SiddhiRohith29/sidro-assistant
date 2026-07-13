import re
from collections import Counter

from .db import get_connection
from .tools import utc_now


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> list[str]:
    stop_words = {
        "about", "after", "again", "also", "because", "before", "could", "from", "have", "into", "that",
        "their", "there", "these", "this", "what", "when", "where", "which", "with", "would", "your", "you",
        "the", "and", "for", "are", "was", "were", "can", "use", "using", "tell", "give", "know", "remember"
    }
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in stop_words]


def create_memory(content: str, source: str = "manual") -> dict:
    cleaned = re.sub(r"\s+", " ", content.strip())
    if not cleaned:
        raise ValueError("Memory content is required.")

    normalized = _normalize(cleaned)
    with get_connection() as conn:
        existing = conn.execute("SELECT * FROM memories ORDER BY id DESC").fetchall()
        for row in existing:
            if _normalize(row["content"]) == normalized:
                return dict(row)

        cursor = conn.execute(
            "INSERT INTO memories (content, source, created_at) VALUES (?, ?, ?)",
            (cleaned, source, utc_now()),
        )
        memory_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return dict(row)


def list_memories() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM memories ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def delete_memory(memory_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0


def search_memories(query: str, limit: int = 6) -> list[dict]:
    query_tokens = _tokens(query)
    memories = list_memories()
    if not query_tokens:
        return memories[:limit]

    query_counter = Counter(query_tokens)
    ranked: list[tuple[float, dict]] = []
    query_text = _normalize(query)
    for item in memories:
        content = item["content"]
        content_tokens = _tokens(content)
        if not content_tokens:
            continue
        content_counter = Counter(content_tokens)
        overlap = sum(min(query_counter[token], content_counter[token]) for token in query_counter)
        phrase_bonus = 3 if _normalize(content) in query_text or query_text in _normalize(content) else 0
        starts_bonus = 1.5 if any(_normalize(content).startswith(token) for token in query_tokens) else 0
        recency_bonus = min(item["id"], 500) / 1000
        score = overlap * 10 + phrase_bonus + starts_bonus + recency_bonus
        if score > 0:
            enriched = dict(item)
            enriched["match_score"] = round(score, 3)
            ranked.append((score, enriched))

    ranked.sort(key=lambda pair: (pair[0], pair[1]["id"]), reverse=True)
    return [item for _, item in ranked[:limit]]