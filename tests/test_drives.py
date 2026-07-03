"""Homeostatic drives: tensions accumulate and decay across loops; safety stays immediate."""

from __future__ import annotations

from yizhi.core.schemas import ThoughtEvent, WillState
from yizhi.engine.drives import update_drives


def _thought(kind: str, salience: float = 0.7) -> ThoughtEvent:
    return ThoughtEvent(kind=kind, content=f"{kind} now", salience=salience)


def test_unresolved_drive_accumulates_then_decays_across_loops():
    state = WillState()
    update_drives([_thought("commitment_pressure")], [], state)
    first = state.drive_state["commitment_pressure"]
    update_drives([_thought("commitment_pressure")], [], state)
    second = state.drive_state["commitment_pressure"]
    assert second >= first                                    # reinforced -> maintained, not reset
    update_drives([], [], state)                              # stop reinforcing
    assert state.drive_state["commitment_pressure"] < second  # unreinforced -> decays


def test_drive_relaxes_away_below_floor():
    state = WillState(drive_state={"curiosity_gap": 0.15})
    update_drives([], [], state)                              # 0.15 * 0.5 = 0.075 < MIN_DRIVE
    assert "curiosity_gap" not in state.drive_state           # relaxed away, dropped


def test_safety_is_immediate_not_accumulated():
    state = WillState()
    drives = update_drives([_thought("safety_pressure", 0.95)], [], state)
    assert any(d.name == "safety_pressure" for d in drives)       # present this step
    assert "safety_pressure" not in state.drive_state            # never persisted (immediate)
    drives2 = update_drives([], [], state)                       # caution gone
    assert not any(d.name == "safety_pressure" for d in drives2)  # immediately absent, no carry


def test_carried_drive_surfaces_without_a_fresh_thought():
    state = WillState()
    update_drives([_thought("curiosity_gap")], [], state)
    drives = update_drives([], [], state)                    # no new thought; carried tension surfaces
    carried = [d for d in drives if d.name == "curiosity_gap"]
    assert carried and "carried tension" in carried[0].reason
