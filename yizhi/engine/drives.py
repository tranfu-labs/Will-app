"""Drive signal updates."""

from __future__ import annotations

from yizhi.core.schemas import DriveSignal, ThoughtEvent, WillState, WorldObservation


DRIVE_BY_THOUGHT = {
    "curiosity_gap": ("curiosity_gap", 0.75),
    "commitment_pressure": ("commitment_pressure", 0.7),
    "safety_pressure": ("safety_pressure", 0.95),
    "maintenance": ("maintenance_pressure", 0.35),
    "identity_continuity": ("continuity_pressure", 0.45),
}

# Drives accumulate across loops (homeostatic), except safety.
SAFETY_DRIVE = "safety_pressure"
DRIVE_DECAY = 0.5   # an unreinforced tension halves each loop (homeostatic relaxation)
MIN_DRIVE = 0.1     # below this a drive has relaxed away and is dropped


def update_drives(
    thoughts: list[ThoughtEvent],
    observations: list[WorldObservation],
    state: WillState,
) -> list[DriveSignal]:
    """Homeostatic drive update: last loop's tensions decay, this loop's thoughts add to them, and
    the result persists on `state.drive_state` — so an unresolved pressure (a commitment never
    closed, a gap never explored) builds across loops instead of resetting every step (it was a
    stateless thought->drive lookup). safety_pressure is the exception: a safety boundary is an
    IMMEDIATE constraint reflecting the current caution, not an accumulating mood, so it is
    recomputed each step and never persisted, keeping the non-negotiable floor crisp."""
    levels = {name: level * DRIVE_DECAY for name, level in state.drive_state.items()}
    reasons: dict[str, str] = {}
    sources: dict[str, list[str]] = {}
    safety: list[DriveSignal] = []
    for thought in thoughts:
        name, base = DRIVE_BY_THOUGHT.get(thought.kind, ("maintenance_pressure", 0.3))
        if name == SAFETY_DRIVE:
            safety.append(DriveSignal(name=name, intensity=min(1.0, max(base, thought.salience)),
                                      reason=thought.content, source_thought_ids=[thought.id]))
            continue
        levels[name] = min(1.0, levels.get(name, 0.0) + max(base, thought.salience))
        reasons[name] = thought.content
        sources.setdefault(name, []).append(thought.id)
    # Persist only the accumulating tensions (never safety) for the next loop.
    state.drive_state = {name: level for name, level in levels.items() if level >= MIN_DRIVE}
    accumulated = [
        DriveSignal(name=name, intensity=level,
                    reason=reasons.get(name, "carried tension from earlier loops"),
                    source_thought_ids=sources.get(name, []))
        for name, level in state.drive_state.items()
    ]
    return safety + accumulated   # safety first, mirroring its non-negotiable priority
