"""Web panel read-side projections (yizhi/web/projections.py).

Pins that the panel derives everything from stored facts: NowView from the
snapshot + newest intention event, task history from the goal-lifecycle events
with snapshot fallback, approvals from approval-request events minus inbox
replies. Pure functions — no db, no fastapi, no network.
"""

from __future__ import annotations

from yizhi.core.schemas import (
    EventType,
    ExistenceBudget,
    Goal,
    GoalStatus,
    Plan,
    PlanStep,
    PlanStepStatus,
    WillState,
)
from yizhi.web.projections import (
    budget_svg_points,
    project_approvals,
    project_chat,
    project_now,
    project_task_history,
)


def _state_with_plan() -> WillState:
    goal = Goal(title="Find a funding edge", description="walk the queue", priority=80)
    plan = Plan(
        goal_id=goal.id,
        cursor=1,
        revision=2,
        stall_count=1,
        steps=[
            PlanStep(description="build dataset", status=PlanStepStatus.DONE),
            PlanStep(description="run sentinel backtests", status=PlanStepStatus.ACTIVE),
            PlanStep(description="summarize packet", status=PlanStepStatus.PENDING),
        ],
    )
    return WillState(
        vision="verified funding-diff knowledge",
        goals=[goal],
        active_plan=plan,
        budget=ExistenceBudget(balance=40.0, initial=100.0, total_spent=70.0, total_replenished=10.0),
        loop_count=7,
        last_surprise=0.4,
    )


def _event(etype: EventType, payload: dict, ts: str, aggregate_id: str = "agg") -> dict:
    return {
        "id": f"event-{ts}-{etype.value}",
        "ts": ts,
        "type": etype.value,
        "aggregate_type": "test",
        "aggregate_id": aggregate_id,
        "payload": payload,
        "correlation_id": f"loop-{ts}",
    }


# --- project_now ---

def test_project_now_without_state_is_empty():
    view = project_now(None, [])
    assert view.has_state is False
    assert view.plan_total == 0


def test_project_now_reads_goal_plan_budget_and_intention():
    events = [
        _event(
            EventType.INTENTION_ACTIVATED,
            {"title": "Probe the queue", "rationale": "evidence replenishes", "endorsed_drive": "curiosity_gap"},
            "2026-07-01T10:00:00+00:00",
        )
    ]
    view = project_now(_state_with_plan(), events)
    assert view.has_state and view.goal_title == "Find a funding edge"
    assert view.goal_status == GoalStatus.PURSUING.value
    assert (view.plan_cursor, view.plan_total, view.plan_pct) == (1, 3, 33)
    assert view.plan_steps[1].is_active and view.plan_steps[0].status == "done"
    assert view.intention_title == "Probe the queue"
    assert view.endorsed_drive == "curiosity_gap"
    assert view.budget_pct == 40 and view.budget_halted is False
    assert 0.0 <= view.budget_pressure <= 1.0
    assert view.loop_count == 7


# --- project_task_history ---

def test_task_history_rebuilds_goal_lifecycle_from_events():
    goal_a = Goal(title="First goal").model_dump()
    goal_b = Goal(title="Second goal").model_dump()
    events = [
        _event(EventType.GOAL_SET, goal_a, "2026-07-01T10:00:00+00:00", goal_a["id"]),
        _event(
            EventType.PLAN_CREATED,
            {"goal_id": goal_a["id"], "revision": 0,
             "steps": [{"description": "s1", "status": "done"}, {"description": "s2", "status": "pending"}]},
            "2026-07-01T10:00:01+00:00",
        ),
        _event(EventType.JUDGMENT_RENDERED, {"verdict": "KILL", "confidence": 0.9}, "2026-07-01T10:00:02+00:00"),
        _event(EventType.GOAL_RETIRED, {"goal_id": goal_a["id"], "status": "done"}, "2026-07-01T10:00:03+00:00"),
        _event(EventType.GOAL_SET, goal_b, "2026-07-01T10:00:04+00:00", goal_b["id"]),
        _event(EventType.JUDGMENT_RENDERED, {"verdict": "INSUFFICIENT"}, "2026-07-01T10:00:05+00:00"),
    ]
    tasks = project_task_history(events, None)
    assert [t.title for t in tasks] == ["Second goal", "First goal"]  # pursuing first, then newest
    first = next(t for t in tasks if t.title == "First goal")
    assert first.status == "done" and first.ended_ts.startswith("2026-07-01T10:00:03")
    assert (first.steps_total, first.steps_done) == (2, 1)
    assert first.verdicts == ["KILL"]  # the judgment inside its window, not the later one
    second = next(t for t in tasks if t.title == "Second goal")
    assert second.status == GoalStatus.PURSUING.value and second.verdicts == ["INSUFFICIENT"]


def test_task_history_falls_back_to_snapshot_goal_and_plan():
    state = _state_with_plan()
    tasks = project_task_history([], state)
    assert len(tasks) == 1
    task = tasks[0]
    assert task.title == "Find a funding edge" and task.status == GoalStatus.PURSUING.value
    assert (task.steps_total, task.steps_done, task.plan_revisions) == (3, 1, 2)


def test_task_history_snapshot_status_overrides_event_status():
    goal = Goal(title="Long runner")
    events = [_event(EventType.GOAL_SET, goal.model_dump(), "2026-07-01T10:00:00+00:00", goal.id)]
    state = _state_with_plan()
    goal.status = GoalStatus.ABANDONED
    state.goals = [goal]
    state.active_plan = None
    tasks = project_task_history(events, state)
    assert tasks[0].status == "abandoned"


# --- project_approvals ---

def test_approvals_split_pending_and_submitted():
    pending = _event(
        EventType.ACTION_PROPOSED,
        {"requires_approval": True, "title": "apply patch"},
        "2026-07-01T10:00:00+00:00",
    )
    answered = _event(
        EventType.ACTION_PROPOSED,
        {"requires_approval": True, "title": "external write"},
        "2026-07-01T09:00:00+00:00",
    )
    plain = _event(EventType.ACTION_PROPOSED, {"requires_approval": False, "title": "git status"}, "2026-07-01T08:00:00+00:00")
    inbox = [f"approve {answered['correlation_id']}", "note thinking out loud"]
    views = project_approvals([plain, answered, pending], inbox)
    assert len(views) == 2  # the non-approval proposal never surfaces
    by_title = {v.title: v for v in views}
    assert by_title["apply patch"].status == "pending"
    assert by_title["external write"].status == "submitted"
    assert views[0].ts >= views[1].ts  # newest first


# --- project_chat ---

def test_chat_merges_inbox_and_outbox_by_time():
    inbox = [
        '{"id": "in-1", "ts": "2026-07-01T10:00:00+00:00", "verb": "ask", "arg": "进展如何？", "raw": "ask 进展如何？"}',
        '{"id": "in-2", "ts": "2026-07-01T10:02:00+00:00", "verb": "vision", "arg": "find edge", "raw": "vision find edge"}',
    ]
    outbox = [
        '{"id": "out-1", "ts": "2026-07-01T10:01:00+00:00", "kind": "report", "title": "回复：进展如何？", "body": "预算 98"}',
        "not json — skipped",
    ]
    messages = project_chat(inbox, outbox)
    assert [(m.role, m.label) for m in messages] == [("human", "ask"), ("agent", "report"), ("human", "vision")]
    assert messages[1].title.startswith("回复")


def test_chat_tail_limit_keeps_newest():
    inbox = [
        f'{{"id": "in-{i}", "ts": "2026-07-01T10:00:{i:02d}+00:00", "verb": "note", "arg": "m{i}", "raw": "note m{i}"}}'
        for i in range(10)
    ]
    messages = project_chat(inbox, [], limit=3)
    assert [m.text for m in messages] == ["m7", "m8", "m9"]


# --- budget svg ---

def test_budget_svg_points_scale_and_edge_cases():
    assert budget_svg_points([]) == ""
    flat = budget_svg_points([("t1", 50.0), ("t2", 50.0)])
    assert len(flat.split()) == 2
    curve = budget_svg_points([("t1", 0.0), ("t2", 100.0)], width=600, height=120)
    first, last = curve.split()
    assert first == "0.0,115.0"          # min value sits near the bottom
    assert last.startswith("600.0,5")    # max value near the top
