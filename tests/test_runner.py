"""Offline tests for the continuous-operation runner.

`run_step` is deterministic with the LLM off (conftest forces it off), so the whole
runner is exercised offline and free: max-steps ceiling, semantic stuck-detection,
the economic budget stop, bounded error isolation, and crash-resume from snapshot.
"""

from __future__ import annotations

from yizhi.core.schemas import EventType
from yizhi.engine.runner import (
    STOP_BUDGET,
    STOP_ERRORS,
    STOP_MAX_STEPS,
    STOP_STUCK,
    detect_stuck,
    run_until,
)
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.state.snapshots import load_or_create_state


def _action_event(command):
    return {"type": EventType.ACTION_PROPOSED.value, "payload": {"command": command, "title": " ".join(command)}}


# ---- detect_stuck (pure) ----

def test_detect_stuck_flags_repeating_action():
    events = [_action_event(["git", "status"]) for _ in range(4)]
    assert detect_stuck(events, window=4) == "repeating-action"
    assert detect_stuck(events[:3], window=4) is None          # not enough yet


def test_detect_stuck_flags_ping_pong():
    a, b = _action_event(["make", "test"]), _action_event(["git", "status"])
    assert detect_stuck([a, b, a, b, a, b, a, b], window=4) == "ping-pong"


def test_detect_stuck_quiet_on_varied_actions():
    events = [_action_event(["a"]), _action_event(["b"]), _action_event(["c"]), _action_event(["d"])]
    assert detect_stuck(events, window=4) is None


# ---- run_until (real deterministic run over self_repo) ----

def test_run_until_stops_at_max_steps(tmp_path):
    # self_repo is static (repeats), so disable stuck-stop to exercise the ceiling.
    db = tmp_path / "run.sqlite"
    state = load_or_create_state(db)
    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=5, stop_on_stuck=False)
    assert outcome.steps == 5
    assert outcome.stop_reason == STOP_MAX_STEPS


def test_run_until_detects_stuck_and_halts_early(tmp_path):
    # self_repo proposes the same action every loop -> repeating-action after `window`.
    db = tmp_path / "run.sqlite"
    state = load_or_create_state(db)
    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=50, stuck_window=4)
    assert outcome.steps == 4                                   # stopped at the window, not 50
    assert outcome.stop_reason.startswith(STOP_STUCK)


def test_run_until_stops_when_budget_depleted(tmp_path):
    # Start near the halt threshold; routine loops net-drain, so it stops on budget,
    # not steps. Disable stuck-stop to isolate the economic stop.
    db = tmp_path / "run.sqlite"
    state = load_or_create_state(db)
    state.budget = state.budget.model_copy(update={"balance": state.budget.halt_threshold + 1.0})
    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=50, stop_on_stuck=False)
    assert outcome.stop_reason == STOP_BUDGET
    assert outcome.steps < 50


def test_run_until_bounded_error_isolation(tmp_path):
    # An environment that always throws must not crash the runner; it stops cleanly
    # after the consecutive-error cap.
    class BoomEnv:
        def observe(self):
            raise RuntimeError("environment down")

        def propose_actions(self, state):
            return []

        def run(self, proposal):
            raise RuntimeError("environment down")

    db = tmp_path / "run.sqlite"
    state = load_or_create_state(db)
    outcome = run_until(BoomEnv(), state, db, max_steps=50, max_consecutive_errors=3)
    assert outcome.steps == 0
    assert outcome.stop_reason == STOP_ERRORS


def test_run_until_resumes_from_snapshot(tmp_path):
    # The snapshot run_step writes each loop is the resume path: a second run_until
    # on the same db continues the same will-state (loop_count keeps climbing).
    db = tmp_path / "run.sqlite"
    first = load_or_create_state(db)
    run_until(SelfRepoEnvironment(), first, db, max_steps=2, stop_on_stuck=False)
    reloaded = load_or_create_state(db)
    assert reloaded.loop_count >= 2                             # state persisted across the runner boundary


# ---- A6: autonomous data-frontier widening on exhaustion ----

def test_run_until_fetch_hook_widens_frontier_instead_of_halting(tmp_path):
    # With a fetch_hook, frontier exhaustion (stuck) WIDENS the data frontier and continues
    # instead of halting — bounded by max_fetches. self_repo re-proposes the same action, so
    # it re-exhausts after each cooldown until the fetch budget is spent. run_step never SSHes.
    from yizhi.state.store import list_events

    db = tmp_path / "run.sqlite"
    state = load_or_create_state(db)
    state.budget = state.budget.model_copy(update={"balance": 1000.0})   # isolate from the budget stop
    calls = {"n": 0}

    def hook() -> bool:
        calls["n"] += 1
        return True                                            # "got genuinely new data"

    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=80, stuck_window=4,
                        fetch_hook=hook, max_fetches=2)
    assert outcome.fetches == 2 and calls["n"] == 2            # widened twice, then bounded
    assert outcome.steps > 4                                   # did NOT halt at the first exhaustion
    assert outcome.stop_reason.startswith(STOP_STUCK)          # halts once the fetch budget is spent
    assert len(list_events(path=db, event_type="DataRequested")) == 2


def test_run_until_barren_fetch_halts(tmp_path):
    # A hook reporting no new data (False) must NOT keep the run alive — exhaustion halts.
    db = tmp_path / "run.sqlite"
    state = load_or_create_state(db)
    state.budget = state.budget.model_copy(update={"balance": 1000.0})
    calls = {"n": 0}

    def hook() -> bool:
        calls["n"] += 1
        return False                                           # nothing new fetched

    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=50, stuck_window=4, fetch_hook=hook)
    assert calls["n"] == 1 and outcome.fetches == 0            # tried once, got nothing
    assert outcome.steps == 4 and outcome.stop_reason.startswith(STOP_STUCK)


def test_run_until_no_hook_halts_unchanged(tmp_path):
    # Default (no fetch_hook) is the prior behavior exactly: exhaustion halts, zero fetches.
    db = tmp_path / "run.sqlite"
    state = load_or_create_state(db)
    outcome = run_until(SelfRepoEnvironment(), state, db, max_steps=50, stuck_window=4)
    assert outcome.fetches == 0 and outcome.steps == 4 and outcome.stop_reason.startswith(STOP_STUCK)
