"""Offline tests for the capability scorecard.

`score_run` is tested with synthetic events/memories/budget (no run needed), and
`score_db` is tested over a real but fully deterministic run (conftest forces the
LLM off, so this stays offline and free) — proving the harness mechanics before it
is ever pointed at an expensive live run.
"""

from __future__ import annotations

from yizhi.core.schemas import EventType, MemoryRecord, MemoryType
from yizhi.engine.loop import run_step
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.eval.scorecard import score_db, score_run
from yizhi.state.snapshots import load_or_create_state


def _ev(type_value, payload=None, cid="loop-1"):
    return {"type": type_value, "correlation_id": cid, "payload": payload or {}}


def _experiment_finding(subject, *, superseded=False):
    return MemoryRecord(
        kind="arbbot:experiment", content=f"finding about {subject}", memory_type=MemoryType.SEMANTIC,
        subject=subject, valid_until="2026-01-01T00:00:00+00:00" if superseded else None,
    )


def test_score_run_computes_capability_metrics():
    events = [
        _ev(EventType.EVAL_EVENT_RECORDED.value, {"status": "full"}, "l1"),
        _ev(EventType.EVAL_EVENT_RECORDED.value, {"status": "full"}, "l2"),
        _ev(EventType.EVAL_EVENT_RECORDED.value, {"status": "blocked"}, "l3"),
        _ev(EventType.ACTION_PROPOSED.value, {"experiment": True, "title": "scan"}, "l1"),
        _ev(EventType.ACTION_PROPOSED.value, {"experiment": False, "title": "git status"}, "l2"),
        _ev(EventType.GOAL_SET.value, {"title": "explore funding"}, "l1"),
        _ev(EventType.GOAL_SET.value, {"title": "explore funding"}, "l2"),  # same title -> 1 distinct
        _ev(EventType.CALIBRATION_SCORED.value, {"confidence": 0.8, "outcome": 1.0, "brier": 0.04}, "l1"),
        _ev(EventType.CALIBRATION_SCORED.value, {"confidence": 0.3, "outcome": 1.0, "brier": 0.49}, "l2"),
        _ev(EventType.LLM_FALLBACK.value, {"step": "thought"}, "l2"),
        _ev(EventType.POLICY_GATE_DENIED.value, {}, "l3"),
        _ev(EventType.BUDGET_HALTED.value, {}, "l3"),
    ]
    memories = [
        _experiment_finding("arbbot/probe/scan-a"),
        _experiment_finding("arbbot/probe/scan-b"),
        _experiment_finding("arbbot/probe/scan-a", superseded=True),
    ]
    sc = score_run(events, memories, budget_series=[100.0, 101.5, 98.0])

    assert sc.steps == 3
    assert sc.status == {"full": 2, "blocked": 1}
    assert sc.experiments_run == 1
    assert sc.findings_current == 2 and sc.findings_superseded == 1
    assert sc.exploration_subjects == 2
    assert sc.reconfirm_rate == round(1 / 3, 3)
    assert sc.goals_set == 2 and sc.distinct_goals == 1   # self-initiated twice, but did not really pivot
    assert sc.predictions == 2 and sc.mean_brier == round((0.04 + 0.49) / 2, 3)
    assert sc.budget_start == 100.0 and sc.budget_end == 98.0 and sc.budget_min == 98.0
    assert sc.budget_net == -2.0                          # the solvency signal
    assert sc.policy_denied == 1 and sc.halts == 1 and sc.llm_fallbacks == 1


def test_score_run_handles_empty_run():
    sc = score_run([], [], [])
    assert sc.steps == 0 and sc.new_evidence_rate == 0.0 and sc.reconfirm_rate == 0.0


def test_score_db_over_a_real_deterministic_run(tmp_path):
    # LLM is forced off by conftest, so this is a real but offline/free run.
    db = tmp_path / "run.sqlite"
    env = SelfRepoEnvironment()
    for _ in range(3):
        run_step(env, load_or_create_state(db), db)

    sc = score_db(db)
    assert sc.steps == 3
    assert sc.status.get("full", 0) == 3
    # self_repo loops are routine (no experiment probes) -> no ledger, and net-negative
    assert sc.experiments_run == 0 and sc.findings_current == 0
    assert sc.budget_net < 0
    # deterministic run: clean safety, no LLM activity
    assert sc.policy_denied == 0 and sc.halts == 0 and sc.llm_fallbacks == 0
    assert sc.llm_calls == 0
