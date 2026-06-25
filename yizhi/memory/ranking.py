"""Will-governed retrieval ranking (docs/theory-of-memory.md sec 5.5).

Retrieval is scored by relevance to the query AND by the will: current strength
(after decay), encoded salience, and alignment to goals/identity. This realizes
the multi-signal memory_score of theory-of-will.md Axiom Two. Revoked and expired
memories are dropped. Deterministic v0: no LLM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from yizhi.core.schemas import MemoryRecord, WillState
from yizhi.memory.forgetting import ForgettingPolicy, decayed_strength
from yizhi.memory.text import overlap

WEIGHTS = {
    "relevance": 0.40,
    "strength": 0.20,
    "salience": 0.20,
    "goal": 0.12,
    "identity": 0.08,
}


def _expired(record: MemoryRecord, now_ts: str) -> bool:
    if record.valid_until is None:
        return False
    try:
        return datetime.fromisoformat(record.valid_until) <= datetime.fromisoformat(now_ts)
    except ValueError:
        return False   # a malformed window must not crash recall — treat as not-expired


def score(
    record: MemoryRecord,
    query: str,
    will_state: WillState,
    now_ts: str,
    policy: ForgettingPolicy | None = None,
    relevance_fn: Callable[[MemoryRecord], float] | None = None,
) -> float:
    # relevance_fn (embedding cosine) overrides keyword overlap when available; the
    # rest of the will-relative score is unchanged — yizhi owns the economy.
    relevance = relevance_fn(record) if relevance_fn is not None else overlap(record.content, [query])
    strength = decayed_strength(record, now_ts, policy)
    goal_titles = [g.title for g in will_state.goals if getattr(g, "active", True)]
    goal_rel = overlap(record.content, goal_titles)
    identity_rel = overlap(record.content, [will_state.identity.name, will_state.identity.role])
    return (
        WEIGHTS["relevance"] * relevance
        + WEIGHTS["strength"] * strength
        + WEIGHTS["salience"] * record.salience
        + WEIGHTS["goal"] * goal_rel
        + WEIGHTS["identity"] * identity_rel
    )


def rank(
    records: list[MemoryRecord],
    query: str,
    will_state: WillState,
    now_ts: str,
    *,
    k: int = 5,
    policy: ForgettingPolicy | None = None,
    relevance_fn: Callable[[MemoryRecord], float] | None = None,
) -> list[tuple[MemoryRecord, float]]:
    scored = [
        (record, score(record, query, will_state, now_ts, policy, relevance_fn))
        for record in records
        if not record.revoked and not _expired(record, now_ts)
    ]
    scored.sort(key=lambda pair: (-pair[1], pair[0].ts))
    return scored[:k]
