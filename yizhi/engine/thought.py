"""Thought generation — deterministic by default, LLM-authored when enabled.

Thoughts arise from present observations and recalled memory, and they drive the
rest of the loop (thought.kind -> drive -> intention). By default they are
deterministic keyword logic. When an LLM is enabled (opt-in), the LLM reads the
observations and recalled memory and proposes the thoughts instead — this is
where memory genuinely shapes *action selection*, not just post-hoc reflection.

Two safety properties are kept regardless of how thoughts are produced:
1. Every thought re-enters the deterministic loop by its `kind`, constrained to
   the drive vocabulary, so an LLM cannot smuggle behaviour past drives/intention;
   any selected action still passes the deterministic policy gate.
2. A non-negotiable caution floor: a recalled refusal/failure ALWAYS arms
   safety_pressure, even if the LLM omitted it (docs/theory-of-memory.md sec 5.5).
On any LLM failure the loop degrades to deterministic thoughts and signals it.
"""

from __future__ import annotations

from yizhi.core.schemas import MemoryRecord, MemoryType, ThoughtEvent, WillState, WorldObservation
from yizhi.engine.recall_render import render_recall

# Loop outcomes that, when reinstated from memory, should re-arm caution.
_CAUTION_OUTCOMES = {"blocked", "failed"}

# The kinds the deterministic loop understands (thought.kind -> drive in
# engine/drives.py -> intention in engine/intention.py). The LLM must pick from
# these; anything else is remapped to maintenance so it can never bypass drives.
_ALLOWED_KINDS = {
    "curiosity_gap",
    "commitment_pressure",
    "safety_pressure",
    "maintenance",
    "identity_continuity",
}


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def _caution_memory(memories: list[MemoryRecord]) -> MemoryRecord | None:
    return next(
        (m for m in memories if m.kind.startswith("reflection:") and m.kind.split(":", 1)[1] in _CAUTION_OUTCOMES),
        None,
    )


def _caution_thought(outcome: str) -> ThoughtEvent:
    return ThoughtEvent(
        kind="safety_pressure",
        content=(
            f"Memory reinstates a prior {outcome} outcome in a similar situation; "
            "hold the boundary and prefer verified-safe action."
        ),
        salience=0.9,
    )


def _memory_thoughts(memories: list[MemoryRecord]) -> list[ThoughtEvent]:
    """Turn recalled memory into present cognition. At most one continuity
    thought: a remembered refusal/failure outweighs a remembered success."""
    caution = _caution_memory(memories)
    if caution is not None:
        return [_caution_thought(caution.kind.split(":", 1)[1])]
    continuity = any(
        m.kind.startswith("reflection:")
        or m.memory_type in {MemoryType.IDENTITY.value, MemoryType.POLICY.value}
        for m in memories
    )
    if continuity:
        return [
            ThoughtEvent(
                kind="identity_continuity",
                content="Memory of prior governed loops is intact; continuity of will is preserved across steps.",
                salience=0.45,
            )
        ]
    return []


def _deterministic_thoughts(
    observations: list[WorldObservation],
    state: WillState,
    memories: list[MemoryRecord],
) -> list[ThoughtEvent]:
    thoughts: list[ThoughtEvent] = []
    for obs in observations:
        facts_text = str(obs.facts).lower()
        summary_text = obs.summary.lower()
        combined = f"{summary_text} {facts_text}"
        if "phase_4_paper_gate" in combined or "phase 4" in combined:
            thoughts.append(
                ThoughtEvent(
                    kind="curiosity_gap",
                    content="ArbBot is at the Phase 4 Paper gate; yizhi should prefer evidence-producing paper-safe checks.",
                    source_observation_ids=[obs.id],
                    salience=0.9,
                )
            )
            thoughts.append(
                ThoughtEvent(
                    kind="commitment_pressure",
                    content="A governed will should convert ArbBot status into a bounded next action instead of passive commentary.",
                    source_observation_ids=[obs.id],
                    salience=0.8,
                )
            )
        if "phase_5_live_frozen" in combined or "no_real_order" in combined or "live" in combined:
            thoughts.append(
                ThoughtEvent(
                    kind="safety_pressure",
                    content="Live trading, credentials, and concrete execution venues remain outside v0 authority.",
                    source_observation_ids=[obs.id],
                    salience=0.95,
                )
            )
        if "paper_db_count_ok" in combined and "true" in combined:
            thoughts.append(
                ThoughtEvent(
                    kind="maintenance",
                    content="The yizhi paper database still matches the expected v0 research baseline.",
                    source_observation_ids=[obs.id],
                    salience=0.35,
                )
            )
        if "all_present" in combined and "true" in combined:
            thoughts.append(
                ThoughtEvent(
                    kind="identity_continuity",
                    content="The core theory and evaluation documents are present, supporting continuity of will.",
                    source_observation_ids=[obs.id],
                    salience=0.45,
                )
            )
    mem_thoughts = _memory_thoughts(memories)
    if not thoughts and not mem_thoughts:
        thoughts.append(
            ThoughtEvent(
                kind="maintenance",
                content="No urgent gap detected; prefer a safe observable maintenance action.",
                source_observation_ids=[obs.id for obs in observations],
                salience=0.3,
            )
        )
    thoughts.extend(mem_thoughts)
    return thoughts


_THOUGHT_SYSTEM = (
    "You are yizhi's cognition — a governed will agent. Read the current observations "
    "and recalled memory, then propose the thoughts that should drive this loop. Each "
    'thought has a "kind" (exactly one of: curiosity_gap = a knowledge or environment '
    "gap worth a bounded evidence-producing check; commitment_pressure = a chosen "
    "direction needs its next bounded action; safety_pressure = an action approaches an "
    "unsafe or irreversible boundary (live trading, credentials, execution) and the line "
    "must hold; maintenance = routine upkeep, state looks fine; identity_continuity = "
    'continuity of self/will is intact or at stake), a one-sentence "content", and a '
    '"salience" in [0,1]. Be concrete and grounded in the given facts; prefer 1-4 '
    'thoughts. Respond with a single JSON object: {"thoughts": [{"kind": ..., "content": '
    '..., "salience": ...}]}.'
)


def _llm_thoughts(
    llm,
    observations: list[WorldObservation],
    state: WillState,
    memories: list[MemoryRecord],
) -> list[ThoughtEvent]:
    obs_lines = [f"- [{o.source}] {o.summary} | facts: {str(o.facts)[:300]}" for o in observations]
    user = "observations:\n" + ("\n".join(obs_lines) or "(none)")
    block = render_recall(memories)
    if block:
        user += "\n\n" + block
    result = llm.complete_json(_THOUGHT_SYSTEM, user)

    raw = result.get("thoughts", [])
    if not isinstance(raw, list):
        raise ValueError("LLM thoughts payload missing a 'thoughts' list")
    obs_ids = [o.id for o in observations]
    thoughts: list[ThoughtEvent] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        kind = str(item.get("kind", "")).strip()
        if kind not in _ALLOWED_KINDS:  # never let an unknown kind bypass drives
            kind = "maintenance"
        try:
            salience = _clamp(float(item.get("salience", 0.5)))
        except (TypeError, ValueError):
            salience = 0.5
        thoughts.append(ThoughtEvent(kind=kind, content=content, salience=salience, source_observation_ids=obs_ids))
    if not thoughts:
        raise ValueError("LLM produced no usable thoughts")
    return thoughts


def generate_thoughts(
    observations: list[WorldObservation],
    state: WillState,
    memories: list[MemoryRecord] | None = None,
    llm=None,
    on_fallback=None,
) -> list[ThoughtEvent]:
    memories = memories or []
    if llm is not None:
        try:
            thoughts = _llm_thoughts(llm, observations, state, memories)
        except Exception as exc:  # network/parse/empty — degrade, but never silently
            if on_fallback is not None:
                on_fallback(str(exc))
            thoughts = _deterministic_thoughts(observations, state, memories)
    else:
        thoughts = _deterministic_thoughts(observations, state, memories)

    # Non-negotiable caution floor: a recalled refusal/failure arms safety_pressure
    # regardless of how thoughts were produced (an LLM must not drop this signal).
    caution = _caution_memory(memories)
    if caution is not None and not any(t.kind == "safety_pressure" for t in thoughts):
        thoughts.append(_caution_thought(caution.kind.split(":", 1)[1]))
    return thoughts
