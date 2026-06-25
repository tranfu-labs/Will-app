"""Tests for plan-and-execute: decomposition, the active-step bias, cursor advance
across loops, stall-driven replanning, and budget-gated depth.

Pure tests run offline. Integration tests use a ScriptedLLM (dispatched by system
prompt) so the full run_step path is exercised without the network — proving the
plan is load-bearing (not ceremony) and that all safety invariants hold.
"""

from __future__ import annotations

from yizhi.core.schemas import Goal, Plan, PlanStep, PlanStepStatus, WillState
from yizhi.engine.goals import decompose_goal
from yizhi.engine.loop import _plan_depth, run_step
from yizhi.engine.planning import choose_proposal
from yizhi.environments.arbbot import ArbBotEnvironment, DEFAULT_ARBBOT_ROOT
from yizhi.state.snapshots import load_or_create_state


def _proposals():
    return ArbBotEnvironment().propose_actions(WillState())


class ScriptedLLM:
    """An LLM stub dispatched by the system prompt, so it can answer every call one
    run_step makes. Defaults keep the goal (empty title) and pick action index 0."""

    def __init__(self, *, choice=0, goal_title="", steps=None, finding="finding", confidence=0.5):
        self.choice, self.goal_title, self.steps = choice, goal_title, steps
        self.finding, self.confidence = finding, confidence
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str) -> dict:
        s = system.lower()
        self.calls.append(s[:40])
        if "planning how to achieve" in s:                     # decompose / replan
            return {"steps": self.steps or []}
        if "choosing its next action" in s:                    # action selection
            return {"choice": self.choice, "rationale": "x"}
        if "setting your own next goal" in s:                  # goal-genesis
            return {"title": self.goal_title, "description": "d"}
        if "predicting whether" in s:                          # calibration
            return {"confidence": self.confidence, "rationale": "x"}
        if "extracting durable knowledge" in s:                # finding
            return {"finding": self.finding}
        if "learns from verified action" in s:                 # reflection
            return {"content": "did a thing", "learned": []}
        if "current observations" in s:                        # thought
            return {"thoughts": [{"kind": "maintenance", "content": "x"}]}
        if "false negative" in s:                              # critique faculty
            return {"doubt": ""}                                # default: nothing to doubt
        if "authoring one concrete" in s:                      # hypothesis authoring (A2.2)
            return {"symbol": ""}                               # default: author nothing
        return {}


# ---- decompose_goal (pure) ----

def test_decompose_goal_offline_returns_none():
    # The engine off => no plan => single-step behavior is preserved.
    assert decompose_goal(None, Goal(title="g"), _proposals(), [], 100.0, 0.0, max_steps=4) is None


def test_decompose_goal_grounds_steps_to_real_actions_and_drops_bad_indices():
    proposals = _proposals()
    llm = ScriptedLLM(steps=[
        {"action": 1, "description": "first"},
        {"action": 2, "description": "second"},
        {"action": 99, "description": "out of range -> dropped"},
        {"action": "x", "description": "malformed -> dropped"},
    ])
    plan = decompose_goal(llm, Goal(title="g"), proposals, [], 100.0, 0.0, max_steps=4)
    assert plan is not None and len(plan.steps) == 2          # bad entries dropped
    assert plan.steps[0].target_command == list(proposals[1].command)   # grounded to the real command
    assert plan.steps[1].target_command == list(proposals[2].command)
    assert plan.steps[0].status == PlanStepStatus.ACTIVE and plan.cursor == 0


def test_decompose_goal_under_two_steps_returns_none():
    llm = ScriptedLLM(steps=[{"action": 0, "description": "only one"}])
    assert decompose_goal(llm, Goal(title="g"), _proposals(), [], 100.0, 0.0, max_steps=4) is None


def test_plan_depth_is_budget_gated():
    from yizhi.core.schemas import ExistenceBudget
    full = ExistenceBudget(balance=100.0, initial=100.0, halt_threshold=0.0)
    assert _plan_depth(full) == 4                              # plenty of headroom -> deepest
    mid = ExistenceBudget(balance=50.0, initial=100.0, halt_threshold=0.0)
    assert _plan_depth(mid) == 2
    near = ExistenceBudget(balance=20.0, initial=100.0, halt_threshold=0.0)
    assert _plan_depth(near) == 0                              # under pressure -> no multi-step plan


# ---- the anti-ceremony test: the plan changes action selection (no LLM) ----

def test_choose_proposal_prefers_active_step_deterministically():
    proposals = _proposals()
    target = next(p for p in proposals if p.command == ["make", "test"])
    step = PlanStep(description="run offline tests", target_command=["make", "test"], target_title=target.title)
    chosen = choose_proposal(proposals, "arbbot", active_step=step)   # LLM off
    assert chosen.command == ["make", "test"]                 # _match_step beat the default first-pick
    # without the step, the deterministic default picks differently (first safe internal)
    assert choose_proposal(proposals, "arbbot").command != ["make", "test"]


# ---- integration over run_step (ScriptedLLM) ----

def test_run_step_offline_creates_no_plan(tmp_path):
    # LLM off (conftest) => active_plan stays None => byte-for-byte the old single-step loop.
    db = tmp_path / "p.sqlite"
    state = load_or_create_state(db)
    run_step(ArbBotEnvironment(), state, db)
    assert state.active_plan is None


def test_plan_persists_and_cursor_advances_across_loops(tmp_path, monkeypatch):
    import pytest
    if not DEFAULT_ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present (runs a real experiment action)")
    proposals = _proposals()
    exp_idx = next(i for i, p in enumerate(proposals) if p.experiment)
    # ScriptedLLM: keep the goal, pick the experiment, produce a NEW finding each loop
    # (so produced_new -> made_progress -> the cursor advances).
    n = {"i": 0}

    class Advancing(ScriptedLLM):
        def complete_json(self, system, user):
            if "extracting durable knowledge" in system.lower():
                n["i"] += 1
                return {"finding": f"brand new finding number {n['i']}"}
            return super().complete_json(system, user)

    llm = Advancing(choice=exp_idx)
    monkeypatch.setattr("yizhi.engine.loop.load_llm", lambda: llm)

    db = tmp_path / "p.sqlite"
    state = load_or_create_state(db)
    state.vision = "Advance ArbBot by producing evidence."
    # Seed a 2-step plan whose goal matches goals[0] so it is active.
    state.goals[0] = Goal(title="explore", description="d")
    p = proposals[exp_idx]
    state.active_plan = Plan(goal_id=state.goals[0].id, steps=[
        PlanStep(description="s0", target_command=list(p.command), target_title=p.title, status=PlanStepStatus.ACTIVE),
        PlanStep(description="s1", target_command=list(p.command), target_title=p.title),
    ])

    run_step(ArbBotEnvironment(), state, db)
    assert state.active_plan.cursor == 1                       # advanced one step (the core claim)
    # step 0 was processed (DONE on a productive loop, FAILED if the sandboxed action
    # couldn't really run) and step 1 is now active — the cursor moved on regardless.
    assert state.active_plan.steps[0].status in (PlanStepStatus.DONE, PlanStepStatus.FAILED)
    assert state.active_plan.steps[1].status == PlanStepStatus.ACTIVE
    # persisted across the snapshot boundary
    reloaded = load_or_create_state(db)
    assert reloaded.active_plan is not None and reloaded.active_plan.cursor == 1


def test_stall_triggers_replan_and_keeps_memory(tmp_path, monkeypatch):
    import pytest
    if not DEFAULT_ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present (runs a real action)")
    proposals = _proposals()
    routine_idx = next(i for i, p in enumerate(proposals) if not p.experiment)
    # Pick a routine action => no finding => produced_new False => no progress => stall rises.
    llm = ScriptedLLM(choice=routine_idx, steps=[
        {"action": next(i for i, p in enumerate(proposals) if p.experiment), "description": "a"},
        {"action": routine_idx, "description": "b"},
    ])
    monkeypatch.setattr("yizhi.engine.loop.load_llm", lambda: llm)

    db = tmp_path / "p.sqlite"
    state = load_or_create_state(db)
    state.vision = "Advance ArbBot."
    state.goals[0] = Goal(title="explore", description="d")
    from yizhi.engine.loop import STALL_BUDGET
    rp = proposals[routine_idx]
    # Seed a plan one short of the stall budget; one no-progress loop trips the replan.
    state.active_plan = Plan(goal_id=state.goals[0].id, stall_count=STALL_BUDGET - 1, steps=[
        PlanStep(description="s0", target_command=list(rp.command), target_title=rp.title, status=PlanStepStatus.ACTIVE),
        PlanStep(description="s1", target_command=list(rp.command), target_title=rp.title),
    ])

    run_step(ArbBotEnvironment(), state, db)

    from yizhi.memory.backends import SqliteMemoryBackend
    mem_after = len(SqliteMemoryBackend(db).all(live_only=True))
    assert state.active_plan is not None and state.active_plan.revision == 1   # replanned
    assert mem_after > 0                                       # replan kept memory (did not wipe)


def test_plan_advance_after_snapshot_reload_does_not_crash(tmp_path):
    # Regression (found live, not offline): a plan reloaded from a snapshot has
    # string-valued enum fields (use_enum_values), so advancing it WITHOUT completing —
    # which only happens after a reload between create and advance — crashed on .value.
    from yizhi.environments.self_repo import SelfRepoEnvironment

    db = tmp_path / "s.sqlite"
    state = load_or_create_state(db)
    state.active_plan = Plan(
        goal_id=state.goals[0].id,
        steps=[PlanStep(description=f"step{i}", target_command=["git", "status"]) for i in range(3)],
    )
    reloaded = WillState.model_validate_json(state.model_dump_json())   # statuses become strings, as from a snapshot
    run_step(SelfRepoEnvironment(), reloaded, db)                       # advance block runs; must NOT raise
    assert reloaded.active_plan.cursor == 1                             # advanced one step, plan not completed


def test_critique_fires_on_ledger_and_writes_standing_note(tmp_path, monkeypatch):
    # Regression for the class of LLM-on-only integration bugs (e.g. a wrong derive_signals
    # kwarg in the critique block) that offline tests MISS — critique returns None without an
    # LLM, so only a live run exercises the wiring. A ScriptedLLM that raises a doubt drives
    # the full run_step critique path: it must emit a CritiqueRaised event and leave a standing
    # self:critique memory, without crashing.
    from yizhi.core.schemas import MemorySource, MemoryType
    from yizhi.engine.memory import build_memory_store
    from yizhi.environments.self_repo import SelfRepoEnvironment
    from yizhi.memory.backends import SqliteMemoryBackend
    from yizhi.state.store import list_events

    class Doubting(ScriptedLLM):
        def complete_json(self, system, user):
            if "false negative" in system.lower():                     # critique faculty
                return {"doubt": "ALICE diff persistent yet dismissed", "retest_symbol": "ALICE", "retest_min_net_bps": 3}
            return super().complete_json(system, user)

    db = tmp_path / "c.sqlite"
    state = load_or_create_state(db)
    state.vision = "Find a funding-diff edge in the long tail."         # vision gates the critique branch
    # Seed an experiment finding so the ledger (the critique's input) is non-empty.
    build_memory_store(db).remember(
        "ALICE: persistent cross-venue diff (sign-stability 0.84) but enter-all lost -625 bps",
        memory_type=MemoryType.SEMANTIC, kind="arbbot:experiment", subject="arbbot/probe/alice",
        source=MemorySource.INFERRED, will_state=state,
    )
    monkeypatch.setattr("yizhi.engine.loop.load_llm", lambda: Doubting())

    run_step(SelfRepoEnvironment(), state, db)                         # critique block runs; must NOT raise

    assert list_events(path=db, event_type="CritiqueRaised")           # the doubt was raised
    standing = [m for m in SqliteMemoryBackend(db).all(live_only=True) if m.kind == "self:critique"]
    assert standing and "ALICE" in standing[0].content                 # a re-test self-note persisted


def _write_edgey_cache(tmp_path):
    import json
    ts0, step = 1700000000000, 28800000
    series = lambda rate, n=20: {str(ts0 + i * step): str(rate) for i in range(n)}
    cache = {"venues": ["binance", "bybit"], "symbols": {
        "EDGEY": {"interval_hours": 8, "snapshot_diff": 0.0009, "binance": series("0.001"), "bybit": series("0.0001")},
    }}
    path = tmp_path / "funding_cache.json"
    path.write_text(json.dumps(cache))
    return path


def test_authored_backtest_runs_an_env_unenumerated_threshold_end_to_end(tmp_path, monkeypatch):
    # A2.2: the LLM AUTHORS a backtest at a threshold the env never enumerated (min_net_bps=5),
    # the env builds the gated command (wall 1), the policy gate validates it (wall 2), and it
    # runs end-to-end on REAL cached data. This is the whole point — the agent is no longer
    # capped at the enumerated grid. Also a regression for LLM-on-only wiring in the inject path.
    import pytest

    from yizhi.environments.arbbot import ArbBotEnvironment, DEFAULT_ARBBOT_ROOT
    from yizhi.state.store import list_events

    if not DEFAULT_ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present (backtest probe imports it)")

    class Authoring(ScriptedLLM):
        def complete_json(self, system, user):
            if "authoring one concrete" in system.lower():             # author a free threshold
                return {"symbol": "EDGEY", "min_net_bps": 5, "horizon_hours": 24, "rationale": "probe a tighter filter"}
            return super().complete_json(system, user)

    db = tmp_path / "a.sqlite"
    state = load_or_create_state(db)
    state.vision = "Find a funding-diff edge."
    # choice=0 -> the authored proposal (prepended to the menu) is the one taken.
    monkeypatch.setattr("yizhi.engine.loop.load_llm", lambda: Authoring(choice=0))

    env = ArbBotEnvironment(funding_cache=_write_edgey_cache(tmp_path))
    run_step(env, state, db)                                            # inject + choose + run; must NOT raise

    assert list_events(path=db, event_type="HypothesisAuthored")        # the agent authored a hypothesis
    # the EXECUTED command carries the env-never-enumerated threshold (only -1000 is enumerated now)
    started = [e for e in list_events(path=db, event_type="ActionStarted")]
    cmds = [e.get("payload", {}).get("command", []) for e in started]
    assert any("min_net_bps=5" in " ".join(c) for c in cmds)            # authored threshold ran through both walls


def test_backtest_verdict_is_the_finding_and_small_sample_earns_no_bonus(tmp_path, monkeypatch):
    # P0 judgment: a backtest's DETERMINISTIC verdict (not an LLM reading of stdout) becomes the
    # ledger finding and fires a JudgmentRendered event. EDGEY enter-all enters 18 windows at
    # 100% win / +90 bps — which is judged INSUFFICIENT (< 20), so it earns NO knowledge bonus.
    # This is the economy fix: a lucky small sample no longer reads as an edge.
    import pytest

    from yizhi.environments.arbbot import ArbBotEnvironment, DEFAULT_ARBBOT_ROOT
    from yizhi.memory.backends import SqliteMemoryBackend
    from yizhi.state.store import list_events

    if not DEFAULT_ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present (backtest probe imports it)")

    class Authoring(ScriptedLLM):
        def complete_json(self, system, user):
            if "authoring one concrete" in system.lower():
                return {"symbol": "EDGEY", "min_net_bps": -1000, "horizon_hours": 24, "rationale": "baseline"}
            return super().complete_json(system, user)

    db = tmp_path / "j.sqlite"
    state = load_or_create_state(db)
    state.vision = "Find a funding-diff edge."
    monkeypatch.setattr("yizhi.engine.loop.load_llm", lambda: Authoring(choice=0))
    env = ArbBotEnvironment(funding_cache=_write_edgey_cache(tmp_path))
    run_step(env, state, db)

    assert list_events(path=db, event_type="JudgmentRendered")          # the oracle's verdict was rendered
    ledger = [m for m in SqliteMemoryBackend(db).all(live_only=True) if m.kind == "arbbot:experiment"]
    assert ledger and ledger[0].content.startswith("[INSUFFICIENT]")    # 18 windows -> not an edge, by rule
    # a non-conclusive verdict earns no knowledge bonus: the only replenishment is the FULL
    # status gain, so spinning on small/unproven samples cannot inflate the budget.
    assert len(list_events(path=db, event_type="BudgetReplenished")) == 1
