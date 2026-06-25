"""Deterministic text helpers for the memory economy (no LLM, no network)."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "it",
    "this", "that", "with", "as", "at", "by", "be", "are", "was", "from", "we",
}


def tokens(text: str) -> set[str]:
    """Lowercase content words longer than two characters, minus stopwords."""
    return {t for t in _WORD.findall(text.lower()) if len(t) > 2 and t not in _STOP}


def overlap(text: str, phrases: list[str]) -> float:
    """Fraction of the phrases' content tokens that appear in text, in [0, 1]."""
    phrase_tokens: set[str] = set()
    for phrase in phrases:
        phrase_tokens |= tokens(phrase)
    if not phrase_tokens:
        return 0.0
    return len(tokens(text) & phrase_tokens) / len(phrase_tokens)
