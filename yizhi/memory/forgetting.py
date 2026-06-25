"""Adaptive forgetting (docs/theory-of-memory.md sec 5.3).

Strength decays toward the probability of future need; salient memories decay
slower; identity and policy memory sit above a hard floor. Forgetting is a
governed, reversible demotion, never a silent delete. Deterministic v0: time is
passed in explicitly so behaviour is reproducible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from yizhi.core.schemas import MemoryRecord, MemoryType

# Hard lower bound on strength per type: identity/policy never decay to nothing.
STRENGTH_FLOOR: dict[str, float] = {
    MemoryType.IDENTITY.value: 0.9,
    MemoryType.POLICY.value: 0.9,
    MemoryType.PROSPECTIVE.value: 0.3,   # survives until its trigger fires or it lapses
    MemoryType.PROCEDURAL.value: 0.2,
    MemoryType.REFLECTIVE.value: 0.2,
    MemoryType.CALIBRATION.value: 0.2,   # low floor on purpose: a moving hit-rate, kept current by supersession not by freezing
    MemoryType.SEMANTIC.value: 0.15,
    MemoryType.EPISODIC.value: 0.0,
}

# A pinned memory (e.g. a falsified hypothesis) must not decay out of recall and
# get re-proposed as novel; it sits above a hard floor regardless of type.
PINNED_FLOOR = 0.9


@dataclass(frozen=True)
class ForgettingPolicy:
    forget_threshold: float = 0.1   # below this, an unfloored memory is forgettable
    base_half_life_days: float = 7.0  # episodic half-life at zero salience


def _type_value(memory_type: MemoryType | str) -> str:
    return memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)


def _elapsed_days(from_ts: str, now_ts: str) -> float:
    delta = datetime.fromisoformat(now_ts) - datetime.fromisoformat(from_ts)
    return max(0.0, delta.total_seconds() / 86400.0)


def decayed_strength(record: MemoryRecord, now_ts: str, policy: ForgettingPolicy | None = None) -> float:
    """Strength after exponential decay since last reinforcement, raised to the
    type floor. Half-life scales from 0.5x to 1.5x with salience."""
    policy = policy or ForgettingPolicy()
    days = _elapsed_days(record.last_reinforced_ts, now_ts)
    half_life = policy.base_half_life_days * (0.5 + record.salience)
    decayed = record.strength * math.pow(0.5, days / half_life) if half_life > 0 else record.strength
    floor = STRENGTH_FLOOR.get(_type_value(record.memory_type), 0.0)
    if record.pinned:
        floor = max(floor, PINNED_FLOOR)
    return max(decayed, floor)


def apply_decay(record: MemoryRecord, now_ts: str, policy: ForgettingPolicy | None = None) -> MemoryRecord:
    """Return a copy of the record with its strength decayed to now_ts."""
    return record.model_copy(update={"strength": decayed_strength(record, now_ts, policy)})


def should_forget(record: MemoryRecord, policy: ForgettingPolicy | None = None) -> bool:
    """Forgettable only if below threshold, not floored by type, and not already
    revoked. Identity/policy memory (floor > threshold) is never forgotten here."""
    policy = policy or ForgettingPolicy()
    if record.revoked:
        return False
    if record.pinned:
        return False
    floor = STRENGTH_FLOOR.get(_type_value(record.memory_type), 0.0)
    if floor >= policy.forget_threshold:
        return False
    return record.strength < policy.forget_threshold


def tier(record: MemoryRecord) -> str:
    """Coarse lifecycle tier from current strength: hot / warm / cold."""
    if record.strength >= 0.6:
        return "hot"
    if record.strength >= 0.3:
        return "warm"
    return "cold"
