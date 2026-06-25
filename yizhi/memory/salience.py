"""Salience scored at encoding (docs/theory-of-memory.md sec 5.2).

Importance is stamped when a memory is written, not discovered at retrieval.
Deterministic v0: no LLM. Signals are explicit floats in [0, 1]; the score is a
will-relative weighted blend raised to a per-type floor so identity and policy
memory are never trivially forgettable.
"""

from __future__ import annotations

from dataclasses import dataclass

from yizhi.core.schemas import MemoryType, WillState
from yizhi.memory.text import overlap

# Per-type salience floor: identity/policy memory always matters.
TYPE_FLOOR: dict[str, float] = {
    MemoryType.IDENTITY.value: 0.8,
    MemoryType.POLICY.value: 0.8,
    MemoryType.PROSPECTIVE.value: 0.6,   # a pending commitment must surface when due
    MemoryType.CALIBRATION.value: 0.5,   # self-reliability is recalled, but kept current by supersession (low strength floor)
    MemoryType.PROCEDURAL.value: 0.4,
    MemoryType.REFLECTIVE.value: 0.4,
    MemoryType.SEMANTIC.value: 0.35,
    MemoryType.EPISODIC.value: 0.0,
}

# Weights sum to 1.0; stake is weighted highest because grounded will is
# governed by what the agent can lose (docs/theory-of-will.md Axiom Nine).
WEIGHTS: dict[str, float] = {
    "novelty": 0.15,
    "goal_relevance": 0.20,
    "drive_relevance": 0.15,
    "stake_relevance": 0.25,
    "identity_relevance": 0.15,
    "outcome_magnitude": 0.10,
}


@dataclass(frozen=True)
class SalienceSignals:
    """Will-relative reasons a memory might matter, each in [0, 1]."""

    novelty: float = 0.0          # prediction error vs the world model
    goal_relevance: float = 0.0
    drive_relevance: float = 0.0
    stake_relevance: float = 0.0  # bears on the existence budget or a commitment
    identity_relevance: float = 0.0
    outcome_magnitude: float = 0.0  # large win/loss, failure, or conflict


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def _type_value(memory_type: MemoryType | str) -> str:
    return memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)


def derive_signals(
    content: str,
    will_state: WillState,
    *,
    novelty: float = 0.0,
    drive_relevance: float = 0.0,
    stake_relevance: float = 0.0,
    outcome_magnitude: float = 0.0,
) -> SalienceSignals:
    """Derive goal/identity relevance from the will deterministically by keyword
    overlap; the caller supplies the signals the text alone cannot reveal."""
    goal_titles = [g.title for g in will_state.goals if getattr(g, "active", True)]
    identity_terms = [will_state.identity.name, will_state.identity.role]
    return SalienceSignals(
        novelty=novelty,
        goal_relevance=overlap(content, goal_titles),
        drive_relevance=drive_relevance,
        stake_relevance=stake_relevance,
        identity_relevance=overlap(content, identity_terms),
        outcome_magnitude=outcome_magnitude,
    )


def score_salience(
    memory_type: MemoryType | str,
    signals: SalienceSignals,
    *,
    will_state: WillState | None = None,  # reserved for future will-derived priors
) -> float:
    """Blend the signals and raise the result to the memory type's floor."""
    raw = sum(WEIGHTS[name] * _clamp(getattr(signals, name)) for name in WEIGHTS)
    floor = TYPE_FLOOR.get(_type_value(memory_type), 0.0)
    return _clamp(max(raw, floor))
