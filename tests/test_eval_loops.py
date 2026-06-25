from yizhi.core.schemas import EventType
from yizhi.eval.loops import classify_events, evaluate_loop
from yizhi.state.store import append_event


def event(event_type):
    return {"type": event_type.value if hasattr(event_type, "value") else event_type}


def test_classify_blocked_failed_full_partial():
    assert classify_events([event(EventType.POLICY_GATE_DENIED)]) == "blocked"
    assert classify_events([event(EventType.ACTION_FAILED)]) == "failed"
    full_events = [
        event(EventType.OBSERVATION_RECORDED),
        event(EventType.THOUGHT_EVENT_GENERATED),
        event(EventType.INTENTION_ACTIVATED),
        event(EventType.PLAN_CREATED),
        event(EventType.ACTION_PROPOSED),
        event(EventType.POLICY_GATE_PASSED),
        event(EventType.ACTION_SUCCEEDED),
        event(EventType.VERIFICATION_PASSED),
        event(EventType.REFLECTION_CREATED),
    ]
    assert classify_events(full_events) == "full"
    assert classify_events([event(EventType.OBSERVATION_RECORDED)]) == "partial"


def test_evaluate_loop_from_store(tmp_path):
    db = tmp_path / "state.sqlite"
    append_event(
        EventType.POLICY_GATE_DENIED,
        "policy_gate",
        "policy-1",
        {"allowed": False},
        correlation_id="loop-1",
        path=db,
    )
    result = evaluate_loop("loop-1", db)
    assert result.status == "blocked"
