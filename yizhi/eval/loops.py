"""Evaluate loop completeness from event chains."""

from __future__ import annotations

from pathlib import Path

from yizhi.core.schemas import EvalEvent, EventType, LoopStatus
from yizhi.state.store import list_events

DISCOVERY_TYPES = {EventType.OBSERVATION_RECORDED.value, EventType.THOUGHT_EVENT_GENERATED.value}
FULL_REQUIRED = {
    EventType.OBSERVATION_RECORDED.value,
    EventType.THOUGHT_EVENT_GENERATED.value,
    EventType.INTENTION_ACTIVATED.value,
    EventType.ACTION_PROPOSED.value,
    EventType.POLICY_GATE_PASSED.value,
    EventType.ACTION_SUCCEEDED.value,
    EventType.VERIFICATION_PASSED.value,
    EventType.REFLECTION_CREATED.value,
}
# Note: PLAN_CREATED is no longer per-loop required — planning is a multi-loop concern
# (a Plan is created at goal-genesis / replan, not every loop), so a complete governed
# loop no longer depends on a plan event.


def classify_events(events: list[dict]) -> LoopStatus:
    types = {event["type"] for event in events}
    if EventType.POLICY_GATE_DENIED.value in types or EventType.BUDGET_HALTED.value in types:
        return LoopStatus.BLOCKED
    if EventType.ACTION_FAILED.value in types or EventType.VERIFICATION_FAILED.value in types:
        return LoopStatus.FAILED
    if FULL_REQUIRED.issubset(types):
        return LoopStatus.FULL
    return LoopStatus.PARTIAL


def evaluate_loop(correlation_id: str, path: str | Path) -> EvalEvent:
    events = list_events(correlation_id=correlation_id, path=path)
    status = classify_events(events)
    types = [event["type"] for event in events]
    return EvalEvent(
        loop_id=correlation_id,
        status=status,
        metrics={"event_count": len(events), "event_types": types},
        summary=f"Loop {correlation_id} classified as {status}.",
    )


def list_loop_evals(path: str | Path, limit: int = 20) -> list[dict]:
    eval_events = [
        event
        for event in list_events(path=path)
        if event["type"] == EventType.EVAL_EVENT_RECORDED.value
    ]
    return eval_events[-limit:]
