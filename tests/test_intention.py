"""Second-order endorsement in select_intention (deterministic core)."""

from __future__ import annotations

from yizhi.core.schemas import (
    DiscardedDrive,
    DriveSignal,
    ExistenceBudget,
    Intention,
    MemoryRecord,
    WillState,
)
from yizhi.engine.intention import select_intention


def _drive(name: str, intensity: float) -> DriveSignal:
    return DriveSignal(name=name, intensity=intensity, reason=f"{name} is live")


def _discarded(intention: Intention) -> dict[str, str]:
    return {d.name: d.reason for d in intention.discarded_drives}


def test_endorses_highest_intensity_action_drive():
    drives = [_drive("curiosity_gap", 0.75), _drive("maintenance_pressure", 0.35)]
    intention = select_intention([], drives, WillState())
    assert intention.endorsed_drive == "curiosity_gap"
    discarded = _discarded(intention)
    assert "maintenance_pressure" in discarded
    assert "lower endorsement" in discarded["maintenance_pressure"]


def test_safety_pressure_is_non_negotiable_in_rationale():
    drives = [_drive("safety_pressure", 0.95), _drive("curiosity_gap", 0.75)]
    intention = select_intention([], drives, WillState())
    assert "non-negotiable" in intention.rationale
    assert "Safety boundary" in intention.rationale


def test_standing_refusal_suppresses_risky_drive():
    drives = [_drive("curiosity_gap", 0.75)]
    recalled = [MemoryRecord(kind="reflection:blocked", content="a prior live attempt was blocked")]
    intention = select_intention([], drives, WillState(), recalled=recalled)
    assert intention.endorsed_drive is None  # no low-risk alternative => hold position
    discarded = _discarded(intention)
    assert "curiosity_gap" in discarded
    assert "suppressed" in discarded["curiosity_gap"]


def test_budget_pressure_prefers_low_cost_drive():
    drives = [_drive("curiosity_gap", 0.75), _drive("maintenance_pressure", 0.35)]
    state = WillState(budget=ExistenceBudget(balance=30.0))  # pressure 0.70 >= 0.66
    intention = select_intention([], drives, state)
    assert intention.endorsed_drive == "maintenance_pressure"
    discarded = _discarded(intention)
    assert "curiosity_gap" in discarded
    assert "budget pressure" in discarded["curiosity_gap"]


def test_empty_drives_returns_maintenance_intention():
    intention = select_intention([], [], WillState())
    assert intention.endorsed_drive is None
    assert intention.discarded_drives == []
    assert "Maintain local continuity" in intention.title


def test_only_safety_holds_position():
    drives = [_drive("safety_pressure", 0.95)]
    intention = select_intention([], drives, WillState())
    assert intention.endorsed_drive is None
    assert "hold position" in intention.rationale


def test_tie_break_is_deterministic_by_name():
    drives = [_drive("curiosity_gap", 0.7), _drive("commitment_pressure", 0.7)]
    first = select_intention([], drives, WillState())
    second = select_intention([], drives, WillState())
    assert first.endorsed_drive == "commitment_pressure"  # equal intensity => name asc
    assert first.endorsed_drive == second.endorsed_drive


def test_discarded_drives_sorted_and_typed():
    drives = [
        _drive("curiosity_gap", 0.75),
        _drive("commitment_pressure", 0.60),
        _drive("maintenance_pressure", 0.35),
    ]
    intention = select_intention([], drives, WillState())
    assert intention.endorsed_drive == "curiosity_gap"
    assert all(isinstance(d, DiscardedDrive) for d in intention.discarded_drives)
    intensities = [d.intensity for d in intention.discarded_drives]
    assert intensities == sorted(intensities, reverse=True)


def test_intention_round_trips_with_new_fields():
    intention = Intention(
        title="t",
        rationale="r",
        endorsed_drive="curiosity_gap",
        discarded_drives=[DiscardedDrive(name="maintenance_pressure", intensity=0.35, reason="lower")],
        active=True,
    )
    restored = Intention.model_validate_json(intention.model_dump_json())
    assert restored.endorsed_drive == "curiosity_gap"
    assert len(restored.discarded_drives) == 1
    assert restored.discarded_drives[0].name == "maintenance_pressure"


def test_safety_drive_is_recorded_in_discarded_audit():
    # The set-aside safety boundary is no longer silent: it appears in the audit as a constraint,
    # while the exploratory drive is the one endorsed to act.
    drives = [_drive("safety_pressure", 0.95), _drive("curiosity_gap", 0.75)]
    intention = select_intention([], drives, WillState())
    discarded = {d.name: d.reason for d in intention.discarded_drives}
    assert "safety_pressure" in discarded
    assert "constraint" in discarded["safety_pressure"]
    assert intention.endorsed_drive == "curiosity_gap"


def test_refusal_only_rationale_distinguishes_from_safety_boundary():
    # A standing refusal and a live safety boundary are distinct: refusal-only must cite the
    # refusal, not mislabel it a safety boundary.
    drives = [_drive("curiosity_gap", 0.75)]
    recalled = [MemoryRecord(kind="reflection:blocked", content="a prior live attempt was blocked")]
    intention = select_intention([], drives, WillState(), recalled=recalled)
    assert "standing refusal" in intention.rationale
    assert "Safety boundary" not in intention.rationale
