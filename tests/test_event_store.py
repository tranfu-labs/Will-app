from will.core.schemas import EventType, WillState
from will.ledger.store import append_event, create_snapshot, get_event, init_db, list_events, load_latest_snapshot


def test_event_store_append_list_get_snapshot(tmp_path):
    db = tmp_path / "state.sqlite"
    init_db(db)
    event_id = append_event(
        EventType.CAMPAIGN_STARTED,
        "campaign",
        "btc-mvp",
        {"title": "BTC MVP"},
        correlation_id="campaign-btc-mvp",
        path=db,
    )
    events = list_events(correlation_id="campaign-btc-mvp", path=db)
    assert len(events) == 1
    assert events[0]["id"] == event_id
    assert events[0]["payload"]["title"] == "BTC MVP"
    assert get_event(event_id, path=db)["aggregate_id"] == "btc-mvp"

    state = WillState()
    snapshot_id = create_snapshot(state, path=db)
    assert snapshot_id.startswith("snapshot-")
    loaded = load_latest_snapshot(db)
    assert loaded is not None
    assert loaded.id == state.id


def test_event_store_uses_wal(tmp_path):
    # WAL prevents "database is locked" when CLI, controller, and projections
    # interleave ledger reads/writes under continuous operation.
    import sqlite3

    db = tmp_path / "state.sqlite"
    init_db(db)
    with sqlite3.connect(db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_list_events_bounded_filtered_tail(tmp_path):
    # Bounded, type-filtered, newest-first reads let controllers/projections tail
    # the ledger without re-scanning the whole log.
    db = tmp_path / "state.sqlite"
    init_db(db)
    for i in range(5):
        append_event(EventType.CAMPAIGN_STAGE_ADVANCED, "campaign", f"c{i}", {"cursor": i + 1}, path=db)
        append_event(EventType.TASKRUN_COMPLETED, "taskrun", f"t{i}", {"summary": "x"}, path=db)
    tail = list_events(path=db, event_type=EventType.CAMPAIGN_STAGE_ADVANCED.value, limit=2, newest_first=True)
    assert len(tail) == 2                                              # bounded
    assert all(e["type"] == EventType.CAMPAIGN_STAGE_ADVANCED.value for e in tail)   # filtered
    assert [e["aggregate_id"] for e in tail] == ["c4", "c3"]          # newest first
