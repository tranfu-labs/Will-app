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


def update_drives(
    thoughts: list[ThoughtEvent],
    observations: list[WorldObservation],
    state: WillState,
) -> list[DriveSignal]:
    drives: list[DriveSignal] = []
    for thought in thoughts:
        name, base = DRIVE_BY_THOUGHT.get(thought.kind, ("maintenance_pressure", 0.3))
        drives.append(
            DriveSignal(
                name=name,
                intensity=min(1.0, max(base, thought.salience)),
                reason=thought.content,
                source_thought_ids=[thought.id],
            )
        )
    return drives
