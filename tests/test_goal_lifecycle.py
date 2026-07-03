"""Goal lifecycle: a goal is PURSUED to done/abandoned before genesis sets the next, so the will
persistently advances ONE task across loops instead of overwriting its goal every loop.

Each test is a structured falsifiable proof — it names exactly which behaviour would fail under the
old unconditional overwrite, and why the new PURSUING gate makes it pass."""

from __future__ import annotations

from yizhi.core.schemas import (
    Goal,
    GoalStatus,
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from yizhi.engine.loop import run_step
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.state.snapshots import load_or_create_state
from yizhi.state.store import list_events


class _ScriptedLLM:
    """Minimal scripted LLM: dispatches by system prompt, same pattern as test_planning.ScriptedLLM.
    `goal_title` controls what genesis WOULD set — the PURSUING gate is what blocks it."""

    def __init__(self, goal_title: str = "") -> None:
        self.goal_title = goal_title

    def complete_json(self, system: str, user: str) -> dict:
        s = system.lower()
        if "setting your own next goal" in s:
            return {"title": self.goal_title, "description": "d"}
        if "planning how to achieve" in s:
            return {"steps": []}
        if "choosing its next action" in s:
            return {"choice": 0, "rationale": "x"}
        if "predicting whether" in s:
            return {"confidence": 0.5, "rationale": "x"}
        if "extracting durable knowledge" in s:
            return {"finding": "f"}
        if "learns from verified action" in s:
            return {"content": "did", "learned": []}
        if "current observations" in s:
            return {"thoughts": [{"kind": "maintenance", "content": "x"}]}
        if "false negative" in s:
            return {"doubt": ""}
        if "authoring one concrete" in s:
            return {"symbol": ""}
        return {}


# ---- schema round-trip ----

def test_goal_status_default_is_pursuing():
    assert Goal(title="g").status == GoalStatus.PURSUING


def test_goal_round_trips_with_status():
    for st in GoalStatus:
        g = Goal(title="g", status=st)
        assert Goal.model_validate_json(g.model_dump_json()).status == st


# ---- the core falsifiable proof: a PURSUING goal is not overwritten ----

def test_pursuing_goal_not_overwritten_while_plan_runs(tmp_path, monkeypatch):
    """The LLM tries to set 'A DIFFERENT GOAL' every loop; without the PURSUING gate
    (the old code: `state.goals = [new_goal]` unconditionally) this test FAILS because
    the in-flight plan goes stale. With the gate, genesis is blocked while the current
    goal is PURSUING and the plan advances across loops."""
    monkeypatch.setattr("yizhi.engine.loop.load_llm", lambda: _ScriptedLLM(goal_title="A DIFFERENT GOAL"))

    db = tmp_path / "g.sqlite"
    state = load_or_create_state(db)
    state.vision = "Persistently advance one task."
    goal = Goal(title="keep me", description="d")
    state.goals = [goal]
    state.active_plan = Plan(goal_id=goal.id, steps=[
        PlanStep(description="s0", target_command=["git", "status"], status=PlanStepStatus.ACTIVE),
        PlanStep(description="s1", target_command=["git", "status"]),
    ])

    run_step(SelfRepoEnvironment(), state, db)

    assert state.goals[0].id == goal.id, "goal was overwritten despite PURSUING"
    assert state.goals[0].title == "keep me"
    assert state.goals[0].status == GoalStatus.PURSUING
    assert state.active_plan is not None and state.active_plan.goal_id == goal.id
    assert state.active_plan.cursor == 1
    assert not list_events(path=db, event_type="GoalRetired")
    assert not list_events(path=db, event_type="GoalSet")


# ---- completion: plan exhausted retires the goal, then genesis sets the next ----

def test_completed_plan_retires_goal_then_genesis(tmp_path, monkeypatch):
    """A 1-step plan completes this loop (cursor runs off the end → COMPLETED). The
    lifecycle then retires the goal (DONE) and genesis sets the next one."""
    monkeypatch.setattr("yizhi.engine.loop.load_llm", lambda: _ScriptedLLM(goal_title="the next goal"))

    db = tmp_path / "g.sqlite"
    state = load_or_create_state(db)
    state.vision = "Complete then pivot."
    goal = Goal(title="almost done", description="d")
    state.goals = [goal]
    state.active_plan = Plan(goal_id=goal.id, steps=[
        PlanStep(description="s0", target_command=["git", "status"], status=PlanStepStatus.ACTIVE),
    ])

    run_step(SelfRepoEnvironment(), state, db)

    retired_events = list_events(path=db, event_type="GoalRetired")
    assert retired_events, "finished goal should be retired"
    assert retired_events[0]["payload"]["goal_id"] == goal.id

    set_events = list_events(path=db, event_type="GoalSet")
    assert set_events, "genesis should set the next goal after retirement"
    assert state.goals[0].title == "the next goal"
    assert state.goals[0].status == GoalStatus.PURSUING


# ---- offline: no LLM => deliberation tail is a no-op, goal persists ----

def test_offline_goal_persists_untouched(tmp_path):
    """Without an LLM, `_deliberate_next_goal` is a no-op: no retirement, no genesis,
    the original goal stays."""
    db = tmp_path / "g.sqlite"
    state = load_or_create_state(db)
    goal = Goal(title="offline goal")
    state.goals = [goal]

    run_step(SelfRepoEnvironment(), state, db)

    assert state.goals[0].id == goal.id
    assert state.goals[0].status == GoalStatus.PURSUING
    assert not list_events(path=db, event_type="GoalRetired")
    assert not list_events(path=db, event_type="GoalSet")
