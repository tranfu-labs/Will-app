"""Time helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with timezone."""
    return datetime.now(UTC).isoformat()
