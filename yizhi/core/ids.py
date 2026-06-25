"""Identifier helpers."""

from __future__ import annotations

from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create a stable, human-scannable event or aggregate id."""
    clean = prefix.strip().replace("_", "-")
    return f"{clean}-{uuid4().hex}"
