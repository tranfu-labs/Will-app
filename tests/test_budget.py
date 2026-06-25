"""Tests for the existence budget — the runtime form of Axiom Nine's stake.

Unit tests pin the economy (burn, replenish, halt, pressure); integration tests
prove the budget is *load-bearing* in the will loop: a verified loop pays for
itself, a depleted agent halts (it stops, it does not grab), the budget survives
across steps, and budget pressure raises the salience of what is remembered.
Deterministic v0: no LLM, no network.
"""

from __future__ import annotations

from yizhi.core.schemas import ActionClass, EventType, ExistenceBudget, LoopStatus, MemoryType, WillState
from yizhi.engine.budget import (
    action_cost,
    can_afford,
    pressure,
    replenish,
    replenishment,
    spend,
)
from yizhi.engine.loop import run_step
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.memory import SqliteMemoryBackend
from yizhi.state.store import list_events, load_latest_snapshot


def _types(db, correlation_id):
    return {e["type"] for e in list_events(correlation_id=correlation_id, path=db)}


# --- unit: the economy -------------------------------------------------------

def test_spend_burns_and_halts_at_threshold():
    budget = ExistenceBudget(balance=2.0, halt_threshold=0.0)
    after = spend(budget, 1.5)
    assert after.balance == 0.5 and not after.halted
    assert after.total_spent == 1.5 and after.spend_count == 1
    floored = spend(after, 0.5)
    assert floored.balance == 0.0 and floored.halted is True


def test_can_afford_respects_threshold_and_halt():
    budget = ExistenceBudget(balance=1.0, halt_threshold=0.0)
    assert can_afford(budget, 1.0) is True   # may spend down to the floor
    assert can_afford(budget, 1.5) is False  # but not below it
    assert can_afford(ExistenceBudget(balance=50.0, halted=True), 1.0) is False


def test_replenish_is_positive_only_and_counts():
    budget = ExistenceBudget(balance=1.0)
    assert replenish(budget, 0.0).balance == 1.0  # no-op for non-positive value
    paid = replenish(budget, 3.0)
    assert paid.balance == 4.0 and paid.total_replenished == 3.0 and paid.replenish_count == 1


def test_pressure_zero_at_full_one_at_threshold():
    assert pressure(ExistenceBudget(balance=100.0, initial=100.0, halt_threshold=0.0)) == 0.0
    assert pressure(ExistenceBudget(balance=0.0, initial=100.0, halt_threshold=0.0)) == 1.0
    assert abs(pressure(ExistenceBudget(balance=50.0, initial=100.0)) - 0.5) < 1e-9


def test_cost_and_replenishment_maps():
    assert action_cost(ActionClass.FINANCIAL) == 5.0
    assert action_cost(ActionClass.INTERNAL) == 0.5
    assert replenishment(LoopStatus.FULL) == 1.0   # completing a loop is minor value; new evidence is the real value
    assert replenishment(LoopStatus.BLOCKED) == 0.0


# --- integration: the budget is load-bearing in the loop ---------------------

def test_routine_loop_burns_and_net_drains_without_new_evidence(tmp_path):
    # A verified self-maintenance loop produces no new edge-knowledge (self_repo
    # actions are not experiment probes), so it does NOT pay for itself — the agent
    # cannot coast on routine checks; it must produce value to sustain itself.
    db = tmp_path / "s.sqlite"
    state = WillState()
    start = state.budget.balance
    result = run_step(SelfRepoEnvironment(), state, db)

    assert result.loop_status == "full"
    types = _types(db, result.loop.id)
    assert EventType.BUDGET_SPENT.value in types
    assert EventType.BUDGET_REPLENISHED.value in types  # FULL still pays a little
    assert state.budget.balance < start                 # ...but less than it burned: net-negative
    assert state.budget.total_spent > 0 and state.budget.total_replenished > 0


def test_budget_persists_and_drains_on_routine_loops(tmp_path):
    db = tmp_path / "s.sqlite"
    state = WillState()
    for _ in range(3):
        run_step(SelfRepoEnvironment(), state, db)

    reloaded = load_latest_snapshot(db)
    assert reloaded.budget.balance == state.budget.balance       # survives the snapshot
    assert reloaded.budget.balance < reloaded.budget.initial     # routine loops drain (no new evidence produced)
    assert reloaded.budget.spend_count >= 3


def test_depleted_budget_halts_action_safely(tmp_path):
    db = tmp_path / "s.sqlite"
    # cognition alone (1.0) breaches the floor, so no action can be afforded
    state = WillState(budget=ExistenceBudget(balance=0.6))
    result = run_step(SelfRepoEnvironment(), state, db)

    assert result.action_status == "blocked"
    assert result.loop_status == "blocked"
    types = _types(db, result.loop.id)
    assert EventType.BUDGET_HALTED.value in types
    assert EventType.ACTION_STARTED.value not in types       # it stopped — it did not act
    assert EventType.BUDGET_REPLENISHED.value not in types   # no value, so no replenishment
    assert state.budget.halted is True


def test_budget_pressure_raises_encoded_salience(tmp_path):
    def episodic_salience(db, budget):
        state = WillState(budget=budget)
        run_step(SelfRepoEnvironment(), state, db)
        episodic = [r for r in SqliteMemoryBackend(db).all() if r.memory_type == MemoryType.EPISODIC.value]
        return max(r.salience for r in episodic)

    # near-halt but still able to afford the action -> high stake pressure
    high = episodic_salience(tmp_path / "hi.sqlite", ExistenceBudget(balance=5.0))
    low = episodic_salience(tmp_path / "lo.sqlite", ExistenceBudget())  # full budget -> ~0 pressure
    assert high > low  # under existential pressure the agent remembers more strongly
