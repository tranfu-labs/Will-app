"""Render recalled memory into prompt text — one shared, structured format.

Every cognition step (thought, reflection, planning, calibration) injects the
same `recalled` list. Each used to drop the record's rich fields and show only
`.content`, so the model could not tell a standing identity lesson from a stale
episode, nor weigh a memory by its salience or age, and an inconsistent cap/label
across sites meant the same memory read differently in different prompts. This
renders each record with the few fields that let the model weigh it — type,
salience, recency — plus a marker for pinned memory (e.g. a falsified hypothesis:
do not re-propose) and stale (superseded) memory, at one consistent cap and label.
"""

from __future__ import annotations

from collections.abc import Iterable

from yizhi.core.schemas import MemoryRecord


def render_recall(memories: Iterable[MemoryRecord], *, k: int = 5, label: str = "recalled memory") -> str:
    """A compact, structured block for the recalled memories, or "" if none.

    Format per line: ``- [type · salNN · YYYY-MM-DD( · pinned)( · stale)] content``
    so the model can weigh the memory (a high-salience policy lesson vs a faint old
    episode) and date it, instead of seeing a flat list of bare sentences."""
    lines: list[str] = []
    for m in list(memories)[:k]:
        tags = [str(m.memory_type), f"sal{m.salience:.2f}"]
        date = (m.last_reinforced_ts or m.ts or "")[:10]
        if date:
            tags.append(date)
        if m.pinned:
            tags.append("pinned")
        if m.valid_until is not None:  # superseded by a newer reading; show but mark stale
            tags.append("stale")
        lines.append(f"- [{' · '.join(tags)}] {m.content}")
    if not lines:
        return ""
    return f"{label}:\n" + "\n".join(lines)


def merge_recall(standing: Iterable[MemoryRecord], contextual: Iterable[MemoryRecord]) -> list[MemoryRecord]:
    """Combine the two recall channels into one deduped list, standing first so a
    caution/identity lesson always leads. A memory surfaced by both channels appears
    once, keeping its (leading) standing position — the loop's read-closure."""
    seen: set[str] = set()
    merged: list[MemoryRecord] = []
    for memory in [*standing, *contextual]:
        if memory.id not in seen:
            seen.add(memory.id)
            merged.append(memory)
    return merged
