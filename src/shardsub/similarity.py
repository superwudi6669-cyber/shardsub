from __future__ import annotations

from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    return "".join(text.split()).lower()


def are_similar(a: str, b: str, threshold: float) -> bool:
    normalized_a = normalize_text(a)
    normalized_b = normalize_text(b)
    if normalized_a == normalized_b:
        return True
    return SequenceMatcher(None, normalized_a, normalized_b).ratio() >= threshold
