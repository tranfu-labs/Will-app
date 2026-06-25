from yizhi.core.schemas import EventType, WillState
from yizhi.state.store import append_event, create_snapshot, get_event, init_db, list_events, load_latest_snapshot


def test_event_store_append_list_get_snapshot(tmp_path):
    db = tmp_path / "state.sqlite"
    init_db(db)
    event_id = append_event(
        EventType.OBSERVATION_RECORDED,
        "observation",
        "obs-1",
        {"summary": "ok"},
        correlation_id="loop-1",
        path=db,
    )
    events = list_events(correlation_id="loop-1", path=db)
    assert len(events) == 1
    assert events[0]["id"] == event_id
    assert events[0]["payload"]["summary"] == "ok"
    assert get_event(event_id, path=db)["aggregate_id"] == "obs-1"

    state = WillState()
    snapshot_id = create_snapshot(state, path=db)
    assert snapshot_id.startswith("snapshot-")
    loaded = load_latest_snapshot(db)
    assert loaded is not None
    assert loaded.id == state.id


def test_event_store_uses_wal(tmp_path):
    # WAL prevents "database is locked" when the memory store and event store (same
    # file, separate connections) interleave under continuous operation.
    import sqlite3

    db = tmp_path / "state.sqlite"
    init_db(db)
    with sqlite3.connect(db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_list_events_bounded_filtered_tail(tmp_path):
    # The bounded, type-filtered, newest-first read the loop uses for calibration, so it
    # does not re-scan the whole log every step (the O(loops^2) fix).
    db = tmp_path / "state.sqlite"
    init_db(db)
    for i in range(5):
        append_event(EventType.CALIBRATION_SCORED, "calibration", f"c{i}", {"brier": i / 10}, path=db)
        append_event(EventType.OBSERVATION_RECORDED, "obs", f"o{i}", {"summary": "x"}, path=db)
    tail = list_events(path=db, event_type=EventType.CALIBRATION_SCORED.value, limit=2, newest_first=True)
    assert len(tail) == 2                                              # bounded
    assert all(e["type"] == EventType.CALIBRATION_SCORED.value for e in tail)   # filtered
    assert [e["aggregate_id"] for e in tail] == ["c4", "c3"]          # newest first
