"""SQLite event store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from will.core.ids import new_id
from will.core.schemas import EventType, WillState
from will.core.time import utc_now_iso
from will.ledger.migrations import SCHEMA_SQL

DEFAULT_DB_PATH = Path(".will/state.sqlite")


def _connect(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # WAL + a busy timeout so CLI commands, controller ticks, and projections can
    # interleave ledger reads/writes without spurious "database is locked" errors.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _payload_to_json(payload: dict[str, Any] | BaseModel) -> str:
    if isinstance(payload, BaseModel):
        return payload.model_dump_json()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def init_db(path: str | Path = DEFAULT_DB_PATH) -> Path:
    db_path = Path(path)
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    return db_path


def append_event(
    event_type: EventType | str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any] | BaseModel,
    causation_id: str | None = None,
    correlation_id: str | None = None,
    path: str | Path = DEFAULT_DB_PATH,
) -> str:
    init_db(path)
    event_id = new_id("event")
    ts = utc_now_iso()
    type_value = event_type.value if isinstance(event_type, EventType) else event_type
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO events (
              id, ts, type, aggregate_type, aggregate_id, payload_json,
              causation_id, correlation_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'committed')
            """,
            (
                event_id,
                ts,
                type_value,
                aggregate_type,
                aggregate_id,
                _payload_to_json(payload),
                causation_id,
                correlation_id,
            ),
        )
    return event_id


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    event["payload"] = json.loads(event.pop("payload_json"))
    return event


def list_events(
    correlation_id: str | None = None,
    aggregate_id: str | None = None,
    path: str | Path = DEFAULT_DB_PATH,
    limit: int | None = None,
    event_type: str | None = None,
    newest_first: bool = False,
    after_rowid: int | None = None,
) -> list[dict[str, Any]]:
    init_db(path)
    where: list[str] = []
    params: list[Any] = []
    if correlation_id is not None:
        where.append("correlation_id = ?")
        params.append(correlation_id)
    if event_type is not None:
        where.append("type = ?")
        params.append(event_type)
    if aggregate_id is not None:
        where.append("aggregate_id = ?")
        params.append(aggregate_id)
    if after_rowid is not None:
        # Incremental consumers (the resident daemon's report cursor) read
        # only events appended after their last position.
        where.append("rowid > ?")
        params.append(after_rowid)
    sql = "SELECT rowid, * FROM events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC" if newest_first else " ORDER BY ts ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with _connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_event(row) for row in rows]


def get_event(event_id: str, path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    init_db(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _row_to_event(row) if row else None


def create_snapshot(state: WillState | dict[str, Any], path: str | Path = DEFAULT_DB_PATH) -> str:
    init_db(path)
    snapshot_id = new_id("snapshot")
    ts = utc_now_iso()
    if isinstance(state, WillState):
        state_json = state.model_dump_json()
    else:
        state_json = json.dumps(state, ensure_ascii=False, sort_keys=True)
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO snapshots (id, ts, state_json) VALUES (?, ?, ?)",
            (snapshot_id, ts, state_json),
        )
    append_event(
        EventType.SNAPSHOT_CREATED,
        aggregate_type="snapshot",
        aggregate_id=snapshot_id,
        payload={"snapshot_id": snapshot_id},
        correlation_id=snapshot_id,
        path=path,
    )
    return snapshot_id


def load_latest_snapshot(path: str | Path = DEFAULT_DB_PATH) -> WillState | None:
    init_db(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT state_json FROM snapshots ORDER BY ts DESC LIMIT 1").fetchone()
    if row is None:
        return None
    return WillState.model_validate_json(row["state_json"])
