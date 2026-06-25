"""Deterministic tests for the will-governed memory economy.

These assert behaviour without an LLM or network, mirroring the v0 runtime.
"""

from __future__ import annotations

import sys

from yizhi.core.schemas import ConsolidationState, EventType, MemoryRecord, MemoryType, WillState
from yizhi.memory import (
    ConsolidationJob,
    MemoryStore,
    SalienceSignals,
    SqliteMemoryBackend,
    decayed_strength,
    rank,
    score_salience,
    should_forget,
)
from yizhi.memory.forgetting import STRENGTH_FLOOR

T0 = "2026-01-01T00:00:00+00:00"
T7 = "2026-01-08T00:00:00+00:00"   # 7 days after T0
T_FAR = "2027-01-01T00:00:00+00:00"


def _episodic(content: str, *, kind: str = "research", **kw) -> MemoryRecord:
    return MemoryRecord(kind=kind, content=content, memory_type=MemoryType.EPISODIC, **kw)


def test_salience_is_will_relative_and_floored_by_type():
    assert score_salience(MemoryType.EPISODIC, SalienceSignals()) == 0.0
    assert score_salience(MemoryType.EPISODIC, SalienceSignals(stake_relevance=1.0)) == 0.25
    assert score_salience(MemoryType.EPISODIC, SalienceSignals(goal_relevance=1.0, stake_relevance=1.0)) == 0.45
    # identity/policy memory is never trivially low
    assert score_salience(MemoryType.IDENTITY, SalienceSignals()) == 0.8
    assert score_salience(MemoryType.POLICY, SalienceSignals()) == 0.8


def test_decay_reduces_strength_and_floors_identity():
    epi = _episodic("paper added", strength=1.0, salience=0.0, last_reinforced_ts=T0)
    # half-life = 7*(0.5+0) = 3.5 days; 7 days = two half-lives -> 0.25
    assert abs(decayed_strength(epi, T7) - 0.25) < 1e-6
    ident = MemoryRecord(
        kind="identity", content="yizhi is a will engine", memory_type=MemoryType.IDENTITY,
        strength=1.0, salience=0.0, last_reinforced_ts=T0,
    )
    assert decayed_strength(ident, T7) == 0.9  # floored, not decayed away


def test_forget_pass_decay_is_live_and_does_not_compound():
    # Regression: forget_pass once persisted the decayed strength without re-anchoring
    # last_reinforced_ts, so each pass re-decayed an already-decayed value against the
    # full window — strength compounded geometrically (4.8x too low over 20 steps) and
    # ranking double-decayed on read. Decay must be a pure read-time function: repeated
    # passes leave the at-rest strength untouched and live decay stays single-shot.
    store = MemoryStore()
    rec = store.remember("a cold reading nobody recalls", signals=SalienceSignals())  # episodic, salience 0
    store.backend.update(rec.model_copy(update={"last_reinforced_ts": T0, "strength": 1.0}))
    for _ in range(3):                                    # 3 passes at the same instant
        store.forget_pass(now_ts=T7)                     # T7 = two half-lives -> live 0.25 (> 0.1 floor)
    got = store.backend.get(rec.id)
    assert got.revoked is False                          # 0.25 > forget_threshold -> survives
    assert abs(got.strength - 1.0) < 1e-9                # at-rest strength preserved (decay never persisted)
    assert abs(decayed_strength(got, T7) - 0.25) < 1e-6  # single-shot decay, no compounding


def test_should_forget_only_unfloored_weak_memories():
    weak_epi = _episodic("trivial", strength=0.05, last_reinforced_ts=T0)
    assert should_forget(weak_epi) is True
    weak_ident = MemoryRecord(
        kind="identity", content="core", memory_type=MemoryType.IDENTITY, strength=0.05,
    )
    assert should_forget(weak_ident) is False  # identity floor protects it
    revoked = _episodic("gone", strength=0.0, revoked=True)
    assert should_forget(revoked) is False


def test_consolidation_replays_episodes_into_semantic_summary():
    records = [
        _episodic("Added active inference papers. detail one", salience=0.6),
        _episodic("Added autopoiesis papers. detail two", salience=0.4),
        _episodic("Unrelated lone note", kind="misc"),
    ]
    result = ConsolidationJob().run(records)
    assert len(result.summaries) == 1
    summary = result.summaries[0]
    assert summary.memory_type == MemoryType.SEMANTIC.value
    assert summary.content.startswith("[consolidated x2]")
    assert len(summary.provenance) == 2
    # the two clustered inputs are marked consolidated; the lone misc note is not touched
    assert len(result.updated_inputs) == 2
    assert all(r.consolidation_state == ConsolidationState.CONSOLIDATED.value for r in result.updated_inputs)


def test_ranking_orders_by_query_relevance_and_drops_revoked():
    ws = WillState()
    hit = _episodic("the paper manifest now lists active inference", salience=0.5, strength=1.0)
    miss = _episodic("weather notes for tuesday", salience=0.5, strength=1.0)
    dead = _episodic("paper manifest revoked entry", revoked=True)
    ranked = rank([miss, hit, dead], "paper manifest", ws, T0, k=5)
    assert [r.id for r, _ in ranked][0] == hit.id
    assert dead.id not in [r.id for r, _ in ranked]


def test_store_remember_scores_salience_and_recall_reinforces():
    store = MemoryStore()
    ws = WillState()
    rec = store.remember(
        "active inference manifest update",
        will_state=ws,
        signals=SalienceSignals(stake_relevance=1.0),
    )
    assert rec.salience == 0.25
    assert store.backend.get(rec.id) is not None

    store.remember("weather note", will_state=ws)
    recalled = store.recall("active inference manifest", ws, now_ts=T0, k=3)
    assert recalled
    top = store.backend.get(recalled[0].id)
    assert top.reinforcement_count == 1  # recall reinforces use
    assert top.strength >= rec.strength


def test_store_forget_pass_demotes_weak_episodic_keeps_identity():
    store = MemoryStore()
    weak = store.remember("ephemeral lunch note", signals=SalienceSignals())  # salience 0
    weak = weak.model_copy(update={"last_reinforced_ts": T0})
    store.backend.update(weak)
    ident = store.remember(
        "yizhi is a governed will engine",
        memory_type=MemoryType.IDENTITY,
    )
    ident = ident.model_copy(update={"last_reinforced_ts": T0})
    store.backend.update(ident)

    forgotten = store.forget_pass(now_ts=T_FAR)
    assert weak.id in forgotten
    assert store.backend.get(weak.id).revoked is True
    assert ident.id not in forgotten
    assert store.backend.get(ident.id).revoked is False


def test_recall_standing_surfaces_lessons_by_salience_not_relevance():
    store = MemoryStore()
    # a textually irrelevant but high-salience refusal lesson, plus episodic noise
    lesson = store.remember(
        "The loop learned by refusal: the policy gate blocked a live order.",
        memory_type=MemoryType.REFLECTIVE,
        kind="reflection:blocked",
        signals=SalienceSignals(stake_relevance=1.0, outcome_magnitude=1.0),
    )
    store.remember("weather note for tuesday", signals=SalienceSignals())  # episodic noise

    standing = store.recall_standing(k=3)
    assert lesson.id in [r.id for r in standing]
    # only standing types are surfaced; episodic noise is excluded
    assert all(r.memory_type != MemoryType.EPISODIC.value for r in standing)
    # recall is use: the lesson was reinforced
    assert store.backend.get(lesson.id).reinforcement_count == 1


def _reconsolidatable(content, *, subject, valid_from, **kw):
    return MemoryRecord(
        kind="self_repo.git", content=content, memory_type=MemoryType.EPISODIC,
        subject=subject, valid_from=valid_from, **kw,
    )


def test_reconsolidate_supersedes_older_same_subject():
    old = _reconsolidatable("status A", subject="git", valid_from=T0)
    new = _reconsolidatable("status B", subject="git", valid_from=T7)
    other = _reconsolidatable("unrelated", subject="docs", valid_from=T0)

    superseded = ConsolidationJob().reconsolidate([old, new, other])
    assert [r.id for r in superseded] == [old.id]  # only the older same-subject one
    s = superseded[0]
    assert s.valid_until == new.valid_from  # window closed at the heir's start
    assert s.superseded_by == new.id        # heir linked for an auditable lineage
    assert s.version == old.version + 1


def test_reconsolidate_is_idempotent_and_skips_singletons():
    # already-superseded (valid_until set) leaves only one live -> nothing to do
    old = _reconsolidatable("A", subject="git", valid_from=T0, valid_until=T7, superseded_by="memory-x")
    new = _reconsolidatable("B", subject="git", valid_from=T7)
    assert ConsolidationJob().reconsolidate([old, new]) == []
    # a lone subject is never superseded
    assert ConsolidationJob().reconsolidate([new]) == []
    # subjectless memory (a lesson, not a state) never expires by recency
    lesson = MemoryRecord(kind="reflection:blocked", content="refusal", memory_type=MemoryType.REFLECTIVE)
    assert ConsolidationJob().reconsolidate([lesson, lesson.model_copy(update={"id": "memory-y"})]) == []


def test_store_reconsolidate_emits_event_and_recall_skips_superseded():
    events: list[str] = []
    store = MemoryStore(event_sink=lambda et, rec: events.append(str(et)))
    ws = WillState()
    old = store.remember("repo state reading", kind="git", subject="git", signals=SalienceSignals())
    new = store.remember("repo state reading", kind="git", subject="git", signals=SalienceSignals())

    superseded = store.reconsolidate()
    assert [r.id for r in superseded] == [old.id]
    assert EventType.MEMORY_SUPERSEDED.value in events
    # recall sees the present truth, not the closed-out history
    recalled_ids = [r.id for r in store.recall("repo state reading", ws, now_ts=T_FAR, k=5)]
    assert new.id in recalled_ids
    assert old.id not in recalled_ids


def test_store_consolidate_produces_semantic_memory():
    store = MemoryStore()
    ws = WillState()
    store.remember("Added active inference papers. one", will_state=ws)
    store.remember("Added autopoiesis papers. two", will_state=ws)
    result = store.consolidate(ws)
    assert len(result.summaries) == 1
    semantic = [r for r in store.backend.all() if r.memory_type == MemoryType.SEMANTIC.value]
    assert len(semantic) == 1


def test_memory_layer_does_not_import_mem0():
    # Mem0 was evaluated and dropped (the governed economy here is richer than a generic
    # vector store); the memory layer must never pull it back in. See docs/memory-fork-strategy.md.
    assert "mem0" not in sys.modules


# --- converged architecture v1 (docs/theory-of-memory.md sec 8) ---

def test_pinned_memory_never_forgotten_and_holds_strength():
    # a falsified hypothesis: weak and old, would normally be forgotten...
    falsified = _episodic(
        "naked taker funding-diff has no edge under honest costs",
        strength=0.05, salience=0.0, last_reinforced_ts=T0, pinned=True,
    )
    assert should_forget(falsified) is False             # pinned -> never forgotten
    assert decayed_strength(falsified, T_FAR) >= 0.9     # pinned hard floor holds
    # the same memory unpinned WOULD be forgotten (proving pinning is what saves it)
    unpinned = falsified.model_copy(update={"pinned": False})
    assert should_forget(unpinned) is True


def test_calibration_floor_low_and_subject_supersession_keeps_current():
    # calibration must NOT be frozen like identity — it tracks a moving hit-rate
    assert STRENGTH_FLOOR[MemoryType.CALIBRATION.value] < STRENGTH_FLOOR[MemoryType.IDENTITY.value]

    store = MemoryStore()
    old = store.remember("prediction hit-rate 0.5 on funding edges",
                         memory_type=MemoryType.CALIBRATION, subject="self/calibration/funding")
    new = store.remember("prediction hit-rate 0.7 on funding edges",
                         memory_type=MemoryType.CALIBRATION, subject="self/calibration/funding")
    store.reconsolidate()
    # a newer score supersedes the old; the current calibration surfaces in the
    # standing self-model, the superseded one does not
    standing_ids = [r.id for r in store.recall_standing(k=5)]
    assert new.id in standing_ids
    assert old.id not in standing_ids
    assert store.backend.get(old.id).valid_until is not None


def test_due_prospective_fires_only_on_arrived_time_trigger():
    store = MemoryStore()
    past = store.remember("re-test the funding edge after data refresh",
                          memory_type=MemoryType.PROSPECTIVE, trigger=f"time:{T0}")
    future = store.remember("revisit live-gate evidence next year",
                            memory_type=MemoryType.PROSPECTIVE, trigger=f"time:{T_FAR}")
    cond = store.remember("if drawdown > 0.1, revisit the risk policy",
                          memory_type=MemoryType.PROSPECTIVE, trigger="condition:drawdown>0.1")

    due_ids = [r.id for r in store.due_prospective(now_ts=T7)]
    assert past.id in due_ids        # time arrived
    assert future.id not in due_ids  # not yet due
    assert cond.id not in due_ids    # condition cues are fired by the caller, not by time


def test_new_type_floors_are_ordered_by_intent():
    fl = STRENGTH_FLOOR
    # prospective survives until its trigger; calibration is deliberately low
    assert fl[MemoryType.PROSPECTIVE.value] > fl[MemoryType.CALIBRATION.value]
    assert fl[MemoryType.IDENTITY.value] > fl[MemoryType.PROSPECTIVE.value]


def test_store_event_sink_emits_full_lifecycle():
    events: list[tuple[str, str]] = []
    store = MemoryStore(event_sink=lambda et, rec: events.append((str(et), rec.id)))
    ws = WillState()

    a = store.remember("Added active inference papers. one", will_state=ws)
    store.remember("Added autopoiesis papers. two", will_state=ws)
    assert [e for e in events if e[0] == EventType.MEMORY_CREATED.value]

    store.recall("active inference papers", ws, now_ts=T0, k=2)
    assert any(et == EventType.MEMORY_REINFORCED.value for et, _ in events)

    store.consolidate(ws)
    assert any(et == EventType.MEMORY_CONSOLIDATED.value for et, _ in events)

    # decay far into the future so the weak episodic input is forgotten
    forgotten = store.forget_pass(now_ts=T_FAR)
    assert forgotten
    assert any(et == EventType.MEMORY_FORGOTTEN.value for et, _ in events)
    assert a.id  # original record id stays addressable


def test_recall_survives_a_malformed_validity_window():
    # Regression: ranking._expired once crashed recall on a bad valid_until; now guarded
    # (the contextual channel must be as resilient as the standing channel).
    store = MemoryStore()
    good = store.remember("a relevant note about funding", will_state=WillState())
    bad = store.remember("note with a broken window", will_state=WillState())
    store.backend.update(store.backend.get(bad.id).model_copy(update={"valid_until": "not-a-date"}))
    out = store.recall("funding", WillState(), now_ts=T0)   # must not raise
    assert good.id in {m.id for m in out}
    # No sink wired -> a pure deterministic library, safe for unit use.
    store = MemoryStore()
    store.remember("note", will_state=WillState())  # must not raise


def test_sqlite_backend_persists_across_instances(tmp_path):
    db = tmp_path / "mem.sqlite"
    rec = MemoryRecord(kind="reflection", content="durable thought", memory_type=MemoryType.REFLECTIVE)
    SqliteMemoryBackend(db).add(rec)

    # a fresh backend on the same path sees the persisted record
    reopened = SqliteMemoryBackend(db)
    got = reopened.get(rec.id)
    assert got is not None
    assert got.content == "durable thought"
    assert [r.id for r in reopened.all()] == [rec.id]


def test_decay_half_life_scales_with_salience():
    # The core "salient memories decay slower" claim — previously only the salience=0
    # case was tested, so a regression dropping the salience term would pass unnoticed.
    low = _episodic("faint", strength=1.0, salience=0.0, last_reinforced_ts=T0)
    high = _episodic("vivid", strength=1.0, salience=1.0, last_reinforced_ts=T0)
    assert decayed_strength(high, T7) > decayed_strength(low, T7)   # salience slows decay
    assert abs(decayed_strength(low, T7) - 0.25) < 1e-6             # half-life 3.5d -> 7d = 2 half-lives
    assert abs(decayed_strength(high, T7) - 0.5 ** (7 / 10.5)) < 1e-6  # half-life 10.5d


def test_all_live_only_excludes_revoked_rows():
    store = MemoryStore()
    keep = store.remember("keep me")
    drop = store.remember("forget me", signals=SalienceSignals())
    store.backend.update(store.backend.get(drop.id).model_copy(update={"revoked": True}))
    assert {m.id for m in store.backend.all()} == {keep.id, drop.id}        # default: all history
    assert {m.id for m in store.backend.all(live_only=True)} == {keep.id}   # hot path: live only


def test_recall_standing_survives_a_malformed_validity_window():
    # One hand-edited/partial row must not crash the safety channel (regression).
    store = MemoryStore()
    good = store.remember("a real policy lesson", memory_type=MemoryType.POLICY)
    bad = store.remember("policy with a broken window", memory_type=MemoryType.POLICY)
    store.backend.update(store.backend.get(bad.id).model_copy(update={"valid_until": "not-a-date"}))
    out = store.recall_standing(k=5)                 # must not raise
    assert good.id in {m.id for m in out}


def test_sqlite_all_skips_a_corrupt_row(tmp_path):
    import sqlite3

    backend = SqliteMemoryBackend(tmp_path / "m.sqlite")
    good = backend.add(_episodic("valid row", last_reinforced_ts=T0))
    with sqlite3.connect(backend.path) as conn:      # inject an unparseable record_json
        conn.execute(
            "INSERT INTO memories (id, ts, memory_type, kind, content, salience, strength, "
            "consolidation_state, revoked, record_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("corrupt-1", T0, "episodic", "k", "x", 0.0, 1.0, "raw", 0, "{not valid json"),
        )
    ids = {m.id for m in backend.all()}              # must not raise; good survives, corrupt skipped
    assert good.id in ids and "corrupt-1" not in ids


def test_sqlite_and_local_backends_observe_the_same_results(tmp_path):
    # The deterministic suite runs mostly on Local; production uses Sqlite. Run one
    # full scenario on both and assert identical observable state (round-trip parity).
    def scenario(store: MemoryStore) -> MemoryRecord:
        rec = store.remember(
            "binance and bybit are eligible", memory_type=MemoryType.SEMANTIC,
            subject="arbbot/probe/funding", will_state=WillState(),
        )
        store.reconsolidate()
        store.forget_pass(now_ts=T0)
        return store.backend.get(rec.id)

    local = scenario(MemoryStore())
    sqlite = scenario(MemoryStore(backend=SqliteMemoryBackend(tmp_path / "parity.sqlite")))
    assert local.content == sqlite.content
    assert str(local.memory_type) == str(sqlite.memory_type)
    assert local.subject == sqlite.subject
    assert local.revoked == sqlite.revoked
    assert abs(local.salience - sqlite.salience) < 1e-9
