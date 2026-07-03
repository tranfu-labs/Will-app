"""Read-only data access for the web panel.

Every query opens its own `mode=ro` SQLite connection — the panel process cannot
create, migrate, or write the event store even on bugs (`yizhi.state.store`
helpers all run `init_db` first, so they are deliberately NOT reused here). The
single write the panel performs is appending a human command to the channel
inbox file, which is `LocalInboxChannel`'s documented multi-writer seam; the
inbox cursor file is never touched, so the will loop's `poll()` still sees
everything.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from yizhi.channels.base import InboundCommand, InboundVerb
from yizhi.core.schemas import WillState


def _connect_ro(db_path: str | Path) -> sqlite3.Connection | None:
    path = Path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    event["payload"] = json.loads(event.pop("payload_json"))
    return event


def fetch_events(
    db_path: str | Path,
    event_type: str | None = None,
    limit: int | None = None,
    newest_first: bool = False,
    after_rowid: int | None = None,
) -> list[dict[str, Any]]:
    """Events with their `rowid` attached — the monotonic cursor the SSE tail uses
    (`ts` has second granularity; several events of one loop share it)."""
    conn = _connect_ro(db_path)
    if conn is None:
        return []
    where: list[str] = []
    params: list[Any] = []
    if event_type:
        where.append("type = ?")
        params.append(event_type)
    if after_rowid is not None:
        where.append("rowid > ?")
        params.append(after_rowid)
    sql = "SELECT rowid, * FROM events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY rowid DESC" if newest_first else " ORDER BY rowid ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_row_to_event(row) for row in rows]


def max_event_rowid(db_path: str | Path) -> int:
    conn = _connect_ro(db_path)
    if conn is None:
        return 0
    try:
        row = conn.execute("SELECT COALESCE(MAX(rowid), 0) AS m FROM events").fetchone()
    finally:
        conn.close()
    return int(row["m"])


def latest_state(db_path: str | Path) -> WillState | None:
    conn = _connect_ro(db_path)
    if conn is None:
        return None
    try:
        row = conn.execute("SELECT state_json FROM snapshots ORDER BY ts DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return WillState.model_validate_json(row["state_json"])


def budget_series(db_path: str | Path, limit: int = 300) -> list[tuple[str, float]]:
    """(ts, balance) per snapshot, oldest first — the deliverables page's curve."""
    conn = _connect_ro(db_path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT ts, state_json FROM snapshots ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    series: list[tuple[str, float]] = []
    for row in rows:
        try:
            balance = float(json.loads(row["state_json"])["budget"]["balance"])
        except (KeyError, TypeError, ValueError):
            continue
        series.append((row["ts"], balance))
    series.reverse()
    return series


def read_inbox_lines(channel_root: str | Path) -> list[str]:
    """All inbox lines, cursor untouched — the panel needs 'was this ever answered',
    not 'what is new', and consuming the cursor would starve the will loop."""
    inbox = Path(channel_root) / "inbox.jsonl"
    if not inbox.exists():
        return []
    return inbox.read_text(encoding="utf-8").splitlines()


def read_outbox_lines(channel_root: str | Path) -> list[str]:
    """All outbox lines (agent → human messages) for the conversation view."""
    outbox = Path(channel_root) / "outbox.jsonl"
    if not outbox.exists():
        return []
    return outbox.read_text(encoding="utf-8").splitlines()


def append_inbox(channel_root: str | Path, verb: InboundVerb, arg: str) -> InboundCommand:
    """Append one human command as a JSON line `parse_inbound` round-trips."""
    command = InboundCommand(verb=verb, arg=arg, raw=f"{verb.value} {arg}".strip())
    root = Path(channel_root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "inbox.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(command.model_dump_json() + "\n")
    return command


def load_packet(packet_path: str | Path) -> dict[str, Any] | None:
    path = Path(packet_path)
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None
