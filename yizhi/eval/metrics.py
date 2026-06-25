"""Small metric helpers."""

from __future__ import annotations


def ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
