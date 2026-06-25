"""Intention selection."""

from __future__ import annotations

from yizhi.core.schemas import DriveSignal, Intention, ThoughtEvent, WillState


def select_intention(thoughts: list[ThoughtEvent], drives: list[DriveSignal], state: WillState) -> Intention:
    drive_names = [drive.name for drive in drives]
    thought_ids = [thought.id for thought in thoughts]
    if "safety_pressure" in drive_names and "curiosity_gap" in drive_names:
        title = "Produce paper-safe evidence without crossing live boundaries"
        rationale = "The system observed a valuable external environment and a strong safety boundary."
    elif "curiosity_gap" in drive_names:
        title = "Run a bounded evidence-producing check"
        rationale = "A knowledge or environment gap is salient and can be tested safely."
    else:
        title = "Maintain local continuity and verify state"
        rationale = "No urgent gap dominates; preserve reliability through local checks."
    return Intention(
        title=title,
        rationale=rationale,
        goal_id=state.goals[0].id if state.goals else None,
        source_thought_ids=thought_ids,
        drive_names=drive_names,
        active=True,
    )
