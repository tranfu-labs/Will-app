"""Intention selection — second-order endorsement over competing drives.

The will is not the loudest drive; it is the drive the agent reflectively endorses
(Frankfurt: a second-order volition over first-order desires). select_intention does
this reflectively rather than by lookup: among the live DriveSignals it weighs a
standing refusal (a concrete prior lesson), a non-negotiable safety boundary, budget
pressure, and intensity; it endorses ONE actionable drive (or none, holding position)
and records the drives it set aside, with reasons, so the choice between motives is
auditable instead of silent.

Deterministic by default (llm=None). The llm/recalled/on_fallback kwargs reserve the
seam for an LLM endorsement sandwich (try-LLM -> on_fallback -> this deterministic
core, with safety still non-negotiable, mirroring engine/thought.py); that LLM layer
is intentionally not implemented in this pass.
"""

from __future__ import annotations

from yizhi.core.schemas import (
    DiscardedDrive,
    DriveSignal,
    Intention,
    ThoughtEvent,
    WillState,
)
from yizhi.engine.budget import pressure
from yizhi.engine.thought import _caution_memory

# Drives that reach into the world and can over-reach. A standing refusal (a concrete
# prior blocked/failed) suppresses them toward a lower-risk alternative; a general
# safety boundary, by contrast, only constrains HOW to act (written into the rationale).
RISKY_DRIVES = {"curiosity_gap", "commitment_pressure"}
SAFETY_DRIVE = "safety_pressure"
# Low-cost upkeep, preferred when the existence budget is under pressure.
LOW_COST_DRIVE = "maintenance_pressure"
# Budget-pressure gate; shares the 0.66 band with loop._plan_depth — at/above it the
# agent is close enough to halt to prefer cheap upkeep over an expensive probe.
BUDGET_PRESSURE_HIGH = 0.66

_TITLE_BY_DRIVE = {
    "curiosity_gap": "Run a bounded evidence-producing check",
    "commitment_pressure": "Honor an open commitment with a verified step",
    "maintenance_pressure": "Maintain local continuity and verify state",
    "continuity_pressure": "Preserve identity continuity through a local check",
}
_MAINTENANCE_TITLE = "Maintain local continuity and verify state"


def select_intention(
    thoughts: list[ThoughtEvent],
    drives: list[DriveSignal],
    state: WillState,
    *,
    llm=None,
    recalled: list | None = None,
    on_fallback=None,
) -> Intention:
    """Endorse one competing drive as the will this loop (or hold position), recording
    the set-aside drives with reasons. Deterministic when llm is None."""
    drive_names = [drive.name for drive in drives]
    has_refusal = _caution_memory(recalled or []) is not None
    budget_pressure = pressure(state.budget)
    safety_present = any(d.name == SAFETY_DRIVE for d in drives)

    endorsed, discarded = _endorse(drives, budget_pressure, has_refusal)
    title, rationale = _compose(endorsed, safety_present, has_refusal)

    # Audit the set-aside drives in a stable, intensity-descending order.
    discarded.sort(key=lambda dr: (-dr[0].intensity, dr[0].name))
    return Intention(
        title=title,
        rationale=rationale,
        goal_id=state.goals[0].id if state.goals else None,
        source_thought_ids=[thought.id for thought in thoughts],
        drive_names=drive_names,
        endorsed_drive=endorsed.name if endorsed else None,
        discarded_drives=[
            DiscardedDrive(name=d.name, intensity=d.intensity, reason=reason)
            for d, reason in discarded
        ],
        active=True,
    )


def _endorse(
    drives: list[DriveSignal], budget_pressure: float, has_refusal: bool
) -> tuple[DriveSignal | None, list[tuple[DriveSignal, str]]]:
    """Reflectively pick one actionable drive to endorse (or None => hold position),
    plus the (drive, reason) pairs it set aside. Pure and deterministic: every
    tie-break is by name, never by dict/set iteration order."""
    discarded: list[tuple[DriveSignal, str]] = []
    if not drives:
        return None, discarded

    # A safety boundary is a constraint, not an action: it is never itself endorsed as the
    # thing to do — but it IS recorded in the audit, so the set-aside is never silent.
    safety = next((d for d in drives if d.name == SAFETY_DRIVE), None)
    if safety is not None:
        discarded.append((safety, "held as a constraint, not endorsed as an action"))
    actionable = [d for d in drives if d.name != SAFETY_DRIVE]
    if not actionable:
        return None, discarded

    candidates = actionable
    # A standing refusal is a concrete lesson (a prior blocked/failed loop recalled):
    # it suppresses the risk-taking drives toward a lower-risk alternative. If none is
    # live, hold position rather than repeat what was refused.
    if has_refusal:
        for d in actionable:
            if d.name in RISKY_DRIVES:
                discarded.append((d, "suppressed by a standing refusal"))
        candidates = [d for d in actionable if d.name not in RISKY_DRIVES]
        if not candidates:
            return None, discarded

    # Under existential budget pressure, prefer cheap upkeep over an expensive probe.
    if budget_pressure >= BUDGET_PRESSURE_HIGH:
        low = [d for d in candidates if d.name == LOW_COST_DRIVE]
        if low:
            for d in candidates:
                if d.name != LOW_COST_DRIVE:
                    discarded.append((d, f"deferred under budget pressure {budget_pressure:.2f}"))
            candidates = low

    endorsed = sorted(candidates, key=lambda d: (-d.intensity, d.name))[0]
    for d in candidates:
        if d.name != endorsed.name:
            discarded.append(
                (d, f"lower endorsement than {endorsed.name} (intensity {endorsed.intensity:.2f})")
            )
    return endorsed, discarded


def _compose(endorsed: DriveSignal | None, safety_present: bool, has_refusal: bool) -> tuple[str, str]:
    """Title + rationale for the endorsement. A live safety boundary and a standing refusal
    are distinct constraints (a boundary shapes HOW to act; a refusal is a concrete prior
    lesson), and each, when present, is written into the rationale on its own terms."""
    if endorsed is None:
        title = _MAINTENANCE_TITLE
        rationale = "No actionable drive was endorsed after second-order review; hold position and verify state."
    else:
        title = _TITLE_BY_DRIVE.get(endorsed.name, _MAINTENANCE_TITLE)
        rationale = (
            f"Endorsed '{endorsed.name}' (intensity {endorsed.intensity:.2f}) "
            "on second-order review of the competing drives."
        )
    if safety_present:
        rationale += " Safety boundary is non-negotiable: stay within paper-safe, reversible action."
    if has_refusal:
        rationale += " A standing refusal holds: do not repeat what was previously blocked."
    return title, rationale
