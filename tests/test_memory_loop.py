"""Integration tests: the will loop uses the governed memory economy.

These assert that memory is no longer a direct append but flows through
MemoryStore — written with salience, persisted durably, consolidated on cadence,
and emitted as MEMORY_* events — so memory is the loop's continuity substrate.
Deterministic v0: no LLM, no network.
"""

from __future__ import annotations

from collections import Counter

from yizhi.core.schemas import EventType, MemoryRecord, MemoryType, WillState
from yizhi.engine.drives import update_drives
from yizhi.engine.loop import run_step
from yizhi.engine.memory import CONSOLIDATE_EVERY
from yizhi.engine.thought import generate_thoughts
from yizhi.environments.self_repo import SelfRepoEnvironment
from yizhi.memory import SqliteMemoryBackend
from yizhi.state.store import list_events


def _event_types(db, correlation_id=None):
    return {e["type"] for e in list_events(correlation_id=correlation_id, path=db)}


def _reflection(outcome: str) -> MemoryRecord:
    return MemoryRecord(
        kind=f"reflection:{outcome}",
        content=f"prior {outcome} loop",
        memory_type=MemoryType.REFLECTIVE,
    )


def test_recalled_refusal_reinstates_safety_pressure():
    # A remembered refusal/failure, with no present observation, still arms caution.
    thoughts = generate_thoughts([], WillState(), memories=[_reflection("blocked")])
    assert any(t.kind == "safety_pressure" for t in thoughts)
    # and that thought reaches the drives — memory genuinely shapes will
    drives = update_drives(thoughts, [], WillState())
    assert any(d.name == "safety_pressure" for d in drives)


def test_recalled_failure_outweighs_success():
    thoughts = generate_thoughts(
        [], WillState(), memories=[_reflection("full"), _reflection("failed")]
    )
    kinds = {t.kind for t in thoughts}
    assert "safety_pressure" in kinds
    assert "identity_continuity" not in kinds  # caution wins over continuity


def test_recalled_continuity_without_caution():
    thoughts = generate_thoughts([], WillState(), memories=[_reflection("full")])
    assert any(t.kind == "identity_continuity" for t in thoughts)


def test_no_memory_no_observation_falls_back_to_maintenance():
    thoughts = generate_thoughts([], WillState(), memories=[])
    assert [t.kind for t in thoughts] == ["maintenance"]


def test_step_routes_memory_through_store_and_emits_created(tmp_path):
    db = tmp_path / "state.sqlite"
    state = WillState()
    result = run_step(SelfRepoEnvironment(), state, db)

    # memory is created via the store's sink, not a bespoke append
    assert EventType.MEMORY_CREATED.value in _event_types(db, result.loop.id)
    # the reflective memory id is tracked on the will state
    assert state.memory_ids
    records = SqliteMemoryBackend(db).all()
    assert records  # durably persisted
    assert any(r.memory_type == MemoryType.REFLECTIVE.value for r in records)
    assert any(r.memory_type == MemoryType.EPISODIC.value for r in records)


def test_memory_survives_across_steps(tmp_path):
    db = tmp_path / "state.sqlite"
    state = WillState()
    run_step(SelfRepoEnvironment(), state, db)
    after_first = len(SqliteMemoryBackend(db).all())
    assert after_first > 0

    # a second step reads the same durable store and adds to it (no reset)
    run_step(SelfRepoEnvironment(), state, db)
    after_second = len(SqliteMemoryBackend(db).all())
    assert after_second > after_first
    assert len(state.memory_ids) == 2  # one reflective memory tracked per loop


def test_memory_ids_are_capped_so_snapshots_stay_bounded(tmp_path):
    # Regression: WillState.memory_ids grew without bound (every loop appends, never
    # trims), bloating every snapshot. It is an audit list, so it is capped to recent N.
    from yizhi.engine.loop import MEMORY_IDS_CAP

    db = tmp_path / "state.sqlite"
    state = WillState()
    state.memory_ids = [f"seed-{i}" for i in range(MEMORY_IDS_CAP + 50)]
    run_step(SelfRepoEnvironment(), state, db)
    assert len(state.memory_ids) <= MEMORY_IDS_CAP


def test_second_loop_recalls_and_reinforces_prior_memory(tmp_path):
    db = tmp_path / "state.sqlite"
    state = WillState()
    first = run_step(SelfRepoEnvironment(), state, db)
    # the first loop has nothing to recall, so it reinforces nothing
    assert EventType.MEMORY_REINFORCED.value not in _event_types(db, first.loop.id)

    second = run_step(SelfRepoEnvironment(), state, db)
    # the second loop recalls prior experience and reinforces what it uses
    assert EventType.MEMORY_REINFORCED.value in _event_types(db, second.loop.id)
    reinforced = [r for r in SqliteMemoryBackend(db).all() if r.reinforcement_count > 0]
    assert reinforced  # recall is use; use strengthens


def test_standing_recall_feeds_a_memory_born_thought_at_runtime(tmp_path):
    db = tmp_path / "state.sqlite"
    state = WillState()
    run_step(SelfRepoEnvironment(), state, db)  # loop 1: nothing to recall yet
    second = run_step(SelfRepoEnvironment(), state, db)  # loop 2: standing recall fires

    thoughts = [
        e["payload"]
        for e in list_events(correlation_id=second.loop.id, path=db)
        if e["type"] == EventType.THOUGHT_EVENT_GENERATED.value
    ]
    # a thought that arose from recalled memory (not from a present observation)
    memory_born = [t for t in thoughts if "Memory of prior governed loops" in t["content"]]
    assert memory_born
    assert memory_born[0]["kind"] == "identity_continuity"
    assert memory_born[0]["source_observation_ids"] == []


def test_consolidation_fires_on_cadence(tmp_path):
    db = tmp_path / "state.sqlite"
    state = WillState()
    env = SelfRepoEnvironment()
    for _ in range(CONSOLIDATE_EVERY):
        run_step(env, state, db)

    types = _event_types(db)
    assert EventType.MEMORY_CONSOLIDATED.value in types
    semantic = [r for r in SqliteMemoryBackend(db).all() if r.memory_type == MemoryType.SEMANTIC.value]
    assert semantic  # episodic clusters were replayed into semantic summaries


def test_reconsolidation_keeps_one_current_per_subject(tmp_path):
    db = tmp_path / "state.sqlite"
    state = WillState()
    env = SelfRepoEnvironment()
    for _ in range(3):
        run_step(env, state, db)

    epi = [r for r in SqliteMemoryBackend(db).all() if r.memory_type == MemoryType.EPISODIC.value]
    current = Counter(r.subject for r in epi if r.valid_until is None)
    # each re-observed subject collapses to exactly one current reading...
    assert current
    assert all(count == 1 for count in current.values())
    # ...while prior readings are superseded (kept as history), not deleted
    superseded = [r for r in epi if r.valid_until is not None]
    assert superseded
    assert all(r.superseded_by for r in superseded)
    assert EventType.MEMORY_SUPERSEDED.value in _event_types(db)
