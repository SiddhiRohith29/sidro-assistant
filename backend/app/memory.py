import re
from collections import Counter
from typing import Iterable

from .db import get_connection
from .tools import utc_now

VALID_CATEGORIES = {"general", "preference", "project", "personal", "workflow", "voice"}
VALID_SENSITIVITY = {"normal", "private"}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _tokens(text: str) -> list[str]:
    stop_words = {
        "about", "after", "again", "also", "because", "before", "could", "from", "have", "into", "that",
        "their", "there", "these", "this", "what", "when", "where", "which", "with", "would", "your", "you",
        "the", "and", "for", "are", "was", "were", "can", "use", "using", "tell", "give", "know", "remember",
        "please", "need", "want", "like", "prefer"
    }
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in stop_words]


def _safe_category(category: str | None) -> str:
    value = (category or "general").strip().lower()
    return value if value in VALID_CATEGORIES else "general"


def _safe_sensitivity(sensitivity: str | None) -> str:
    value = (sensitivity or "normal").strip().lower()
    return value if value in VALID_SENSITIVITY else "normal"


def infer_category(content: str) -> str:
    lower = content.lower()
    if any(phrase in lower for phrase in ["i prefer", "i like", "i dislike", "use simple", "keep it", "call me"]):
        return "preference"
    if any(word in lower for word in ["sidro", "project", "build", "github", "frontend", "backend"]):
        return "project"
    if any(phrase in lower for phrase in ["my name", "i am", "i work", "my goal", "my routine"]):
        return "personal"
    if any(word in lower for word in ["voice", "transcribe", "microphone", "tts"]):
        return "voice"
    if any(word in lower for word in ["workflow", "process", "daily", "plan"]):
        return "workflow"
    return "general"


def _row_to_memory(row) -> dict:
    item = dict(row)
    item["pinned"] = bool(item.get("pinned", 0))
    item.setdefault("category", "general")
    item.setdefault("sensitivity", "normal")
    item.setdefault("updated_at", item.get("created_at"))
    return item


def _similarity_score(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 1.0 if _normalize(left) == _normalize(right) else 0.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    phrase_bonus = 0.35 if _normalize(left) in _normalize(right) or _normalize(right) in _normalize(left) else 0
    return round((overlap / union) + phrase_bonus, 3)


def find_similar_memories(content: str, limit: int = 5, threshold: float = 0.34) -> list[dict]:
    cleaned = _clean(content)
    if not cleaned:
        return []
    scored = []
    for item in list_memories(include_private=True):
        score = _similarity_score(cleaned, item["content"])
        if score >= threshold:
            enriched = dict(item)
            enriched["similarity"] = score
            scored.append(enriched)
    scored.sort(key=lambda item: (item["similarity"], item["pinned"], item["id"]), reverse=True)
    return scored[:limit]


def create_memory(
    content: str,
    source: str = "manual",
    category: str | None = None,
    sensitivity: str = "normal",
    pinned: bool = False,
) -> dict:
    cleaned = _clean(content)
    if not cleaned:
        raise ValueError("Memory content is required.")

    normalized = _normalize(cleaned)
    now = utc_now()
    category_value = _safe_category(category or infer_category(cleaned))
    sensitivity_value = _safe_sensitivity(sensitivity)
    pinned_value = 1 if pinned else 0
    with get_connection() as conn:
        existing = conn.execute("SELECT * FROM memories ORDER BY id DESC").fetchall()
        for row in existing:
            if _normalize(row["content"]) == normalized:
                return _row_to_memory(row)

        cursor = conn.execute(
            """
            INSERT INTO memories (content, source, category, sensitivity, pinned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (cleaned, source, category_value, sensitivity_value, pinned_value, now, now),
        )
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_memory(row)


def list_memories(category: str | None = None, include_private: bool = True) -> list[dict]:
    clauses = []
    values = []
    if category:
        clauses.append("category = ?")
        values.append(_safe_category(category))
    if not include_private:
        clauses.append("sensitivity != 'private'")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM memories
            {where}
            ORDER BY pinned DESC, updated_at DESC, id DESC
            """,
            values,
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def update_memory(
    memory_id: int,
    content: str | None = None,
    category: str | None = None,
    sensitivity: str | None = None,
    pinned: bool | None = None,
) -> dict | None:
    updates = []
    values = []
    if content is not None:
        cleaned = _clean(content)
        if not cleaned:
            raise ValueError("Memory content is required.")
        updates.append("content = ?")
        values.append(cleaned)
    if category is not None:
        updates.append("category = ?")
        values.append(_safe_category(category))
    if sensitivity is not None:
        updates.append("sensitivity = ?")
        values.append(_safe_sensitivity(sensitivity))
    if pinned is not None:
        updates.append("pinned = ?")
        values.append(1 if pinned else 0)
    if not updates:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return _row_to_memory(row) if row else None
    updates.append("updated_at = ?")
    values.append(utc_now())
    values.append(memory_id)
    with get_connection() as conn:
        cursor = conn.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", values)
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_memory(row)


def delete_memory(memory_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0


def merge_memories(memory_ids: Iterable[int], content: str, category: str | None = None, sensitivity: str = "normal", pinned: bool = False) -> dict:
    ids = sorted({int(memory_id) for memory_id in memory_ids})
    if len(ids) < 2:
        raise ValueError("Choose at least two memories to merge.")
    merged = create_memory(content, source="merge", category=category, sensitivity=sensitivity, pinned=pinned)
    with get_connection() as conn:
        conn.executemany("DELETE FROM memories WHERE id = ? AND id != ?", [(memory_id, merged["id"]) for memory_id in ids])
    return merged


def search_memories(query: str, limit: int = 6, include_private: bool = False) -> list[dict]:
    query_tokens = _tokens(query)
    memories = list_memories(include_private=include_private)
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
        pinned_bonus = 2 if item.get("pinned") else 0
        recency_bonus = min(item["id"], 500) / 1000
        score = overlap * 10 + phrase_bonus + starts_bonus + pinned_bonus + recency_bonus
        if score > 0:
            enriched = dict(item)
            enriched["match_score"] = round(score, 3)
            ranked.append((score, enriched))

    ranked.sort(key=lambda pair: (pair[0], pair[1]["pinned"], pair[1]["id"]), reverse=True)
    return [item for _, item in ranked[:limit]]


def suggest_from_message(message: str) -> dict | None:
    cleaned = _clean(message)
    lower = cleaned.lower()
    if not cleaned or lower.startswith("remember that"):
        return None
    patterns = [
        r"\bi prefer\b.+",
        r"\bi like\b.+",
        r"\bi dislike\b.+",
        r"\bmy goal is\b.+",
        r"\bmy routine\b.+",
        r"\buse .+ when explaining\b.+",
        r"\bcall me\b.+",
    ]
    if not any(re.search(pattern, lower) for pattern in patterns):
        return None
    if find_similar_memories(cleaned, limit=1, threshold=0.7):
        return None
    existing = list_suggestions(status="pending")
    if any(_normalize(item["content"]) == _normalize(cleaned) for item in existing):
        return None
    return create_suggestion(cleaned, reason="Detected a reusable preference or personal detail.", category=infer_category(cleaned))


def create_suggestion(content: str, reason: str = "", category: str | None = None) -> dict:
    cleaned = _clean(content)
    if not cleaned:
        raise ValueError("Suggestion content is required.")
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memory_suggestions (content, category, reason, status, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (cleaned, _safe_category(category or infer_category(cleaned)), reason.strip(), now, now),
        )
        row = conn.execute("SELECT * FROM memory_suggestions WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_suggestions(status: str = "pending") -> list[dict]:
    safe_status = status if status in {"pending", "accepted", "dismissed", "all"} else "pending"
    with get_connection() as conn:
        if safe_status == "all":
            rows = conn.execute("SELECT * FROM memory_suggestions ORDER BY updated_at DESC, id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memory_suggestions WHERE status = ? ORDER BY updated_at DESC, id DESC",
                (safe_status,),
            ).fetchall()
    return [dict(row) for row in rows]


def accept_suggestion(suggestion_id: int, pinned: bool = False, sensitivity: str = "normal") -> dict | None:
    now = utc_now()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM memory_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE memory_suggestions SET status = 'accepted', updated_at = ? WHERE id = ?",
            (now, suggestion_id),
        )
    created = create_memory(row["content"], source="suggestion", category=row["category"], sensitivity=sensitivity, pinned=pinned)
    return {"suggestion": {**dict(row), "status": "accepted", "updated_at": now}, "memory": created}


def dismiss_suggestion(suggestion_id: int) -> dict | None:
    now = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE memory_suggestions SET status = 'dismissed', updated_at = ? WHERE id = ?",
            (now, suggestion_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM memory_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    return dict(row)
