"""Prospective memory wired through the loop: ITERATE seeds a deferred re-test, a due cue
surfaces into recall, and it fires exactly once (no re-surfacing on later loops)."""

from __future__ import annotations

from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    ActionRecord,
    ActionStatus,
    EnvironmentName,
    MemoryRecord,
    MemoryType,
    VerificationResult,
    WorldObservation,
)
from yizhi.engine.loop import run_step
from yizhi.engine.memory import build_memory_store
from yizhi.engine.recall_render import merge_recall
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.memory.backends import SqliteMemoryBackend
from yizhi.memory.store import MemoryStore
from yizhi.state.snapshots import load_or_create_state

_PAST = "time:2000-01-01T00:00:00+00:00"
_FUTURE = "time:2999-01-01T00:00:00+00:00"
_NOW = "2020-01-01T00:00:00+00:00"


def _prospectives(db):
    return [m for m in SqliteMemoryBackend(db).all(live_only=True)
            if m.memory_type == MemoryType.PROSPECTIVE.value]


# ---- store.fire_prospective (pure) ----

def test_fire_prospective_revokes_so_a_past_due_cue_does_not_resurface():
    store = MemoryStore()
    p = store.remember("re-test X later", memory_type=MemoryType.PROSPECTIVE, trigger=_PAST)
    assert p.id in [r.id for r in store.due_prospective(now_ts=_NOW)]      # past-due -> surfaces
    store.fire_prospective([p])
    assert p.id not in [r.id for r in store.due_prospective(now_ts=_NOW)]  # consumed -> never again


# ---- recall_render.merge_recall (pure) ----

def test_merge_recall_orders_standing_then_due_then_contextual():
    s = MemoryRecord(kind="reflection:blocked", content="caution")
    d = MemoryRecord(kind="arbbot:retest", content="re-test X", memory_type=MemoryType.PROSPECTIVE)
    c = MemoryRecord(kind="episodic", content="ctx")
    merged = merge_recall([s], [c], [d])
    assert [m.id for m in merged] == [s.id, d.id, c.id]   # safety first, due next, context last


# ---- loop: ITERATE seeds a prospective (deterministic, no LLM) ----

class _IterateMetricsEnv:
    """An experiment action returning metrics that judge as ITERATE (net+ but weak Sharpe) — the
    verdict meaning 'tune/widen later'. Uses an allowlisted INTERNAL command so it passes the
    policy gate; the metrics (not the command) drive the judge. No LLM, no ArbBot repo."""
    name = "arbbot"

    def observe(self):
        return [WorldObservation(environment=EnvironmentName.ARBBOT, source="arbbot.bt", summary="probe")]

    def propose_actions(self, state):
        return [ActionProposal(environment=EnvironmentName.ARBBOT, action_class=ActionClass.INTERNAL,
                               title="probe", command=["make", "test"], experiment=True, dry_run=True)]

    def run(self, proposal):
        return ActionRecord(proposal_id=proposal.id, environment=EnvironmentName.ARBBOT,
                            status=ActionStatus.SUCCEEDED, command=proposal.command, exit_code=0,
                            metrics={"n_entered": 30.0, "n_windows": 40.0, "total_realized_bps": 50.0,
                                     "sharpe_like": 0.3, "win_rate": 0.6, "persistence_sign_stability": 0.7,
                                     "min_net_bps": 0.0, "symbol": "EDGEY"})

    def verify(self, record):
        return VerificationResult(action_record_id=record.id, passed=True, summary="ok")


def test_iterate_verdict_seeds_a_retest_prospective(tmp_path):
    db = tmp_path / "i.sqlite"
    state = load_or_create_state(db)
    run_step(_IterateMetricsEnv(), state, db)             # LLM off (conftest)
    prospectives = _prospectives(db)
    assert prospectives                                   # ITERATE scheduled a deferred re-test
    assert prospectives[0].trigger.startswith("time:")    # time-cued
    assert "re-test" in prospectives[0].content


# ---- loop: a due prospective surfaces, then is consumed, leaving the future one intact ----

def test_due_prospective_surfaces_then_consumed_leaving_future_intact(tmp_path):
    db = tmp_path / "e.sqlite"
    state = load_or_create_state(db)
    store = build_memory_store(db)
    store.remember("re-test now", memory_type=MemoryType.PROSPECTIVE, trigger=_PAST, subject="s/past")
    store.remember("re-test later", memory_type=MemoryType.PROSPECTIVE, trigger=_FUTURE, subject="s/future")

    run_step(SelfRepoEnvironment(), state, db)            # the loop calls due_prospective + fire

    live = _prospectives(db)
    assert [m.subject for m in live] == ["s/future"]      # past-due fired (consumed); future kept until its time
