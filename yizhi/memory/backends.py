"""Pluggable memory backends.

yizhi owns the memory *economy* (salience, decay, consolidation, will-ranking);
the backend rents the storage/retrieval *infrastructure*. The v0 default is a
local deterministic store with no LLM and no network. Mem0 is an optional backend
behind the same Protocol, imported lazily, so the deterministic runtime never
requires it. See docs/memory-fork-strategy.md.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable

from yizhi.core.schemas import MemoryRecord


@runtime_checkable
class MemoryBackend(Protocol):
    def add(self, record: MemoryRecord) -> MemoryRecord: ...
    def get(self, memory_id: str) -> MemoryRecord | None: ...
    def update(self, record: MemoryRecord) -> MemoryRecord: ...
    def delete(self, memory_id: str) -> None: ...
    def all(self, *, live_only: bool = False) -> list[MemoryRecord]: ...
    def set_embedding(self, memory_id: str, vector: list[float]) -> None: ...
    def get_embeddings(self, memory_ids: list[str]) -> dict[str, list[float]]: ...


class LocalMemoryBackend:
    """Deterministic in-process backend — the v0 default. No LLM, no network."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryRecord] = {}
        self._embeddings: dict[str, list[float]] = {}

    def add(self, record: MemoryRecord) -> MemoryRecord:
        self._items[record.id] = record
        return record

    def get(self, memory_id: str) -> MemoryRecord | None:
        return self._items.get(memory_id)

    def update(self, record: MemoryRecord) -> MemoryRecord:
        self._items[record.id] = record
        return record

    def delete(self, memory_id: str) -> None:
        self._items.pop(memory_id, None)
        self._embeddings.pop(memory_id, None)

    def all(self, *, live_only: bool = False) -> list[MemoryRecord]:
        return [r for r in self._items.values() if not (live_only and r.revoked)]

    def set_embedding(self, memory_id: str, vector: list[float]) -> None:
        self._embeddings[memory_id] = vector

    def get_embeddings(self, memory_ids: list[str]) -> dict[str, list[float]]:
        return {mid: self._embeddings[mid] for mid in memory_ids if mid in self._embeddings}


class SqliteMemoryBackend:
    """Durable backend on the same SQLite database as the event store, so memory
    survives across `yizhi step` invocations and is auditable. Deterministic and
    local: no LLM, no network."""

    def __init__(self, path: str | Path) -> None:
        from yizhi.state.store import init_db  # local import avoids an import cycle

        self.path = Path(path)
        init_db(self.path)  # ensures the `memories` table exists

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        # WAL + a busy timeout so the memory store and the event store (same file,
        # separate connections) never raise "database is locked" under interleaved
        # access — important for a continuously-running agent.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Connection]:
        """A connection that commits on success and is ALWAYS closed. `with conn`
        alone commits but leaks the (unclosed) connection — over a long run that is a
        steady file-handle leak; this closes every time."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add(self, record: MemoryRecord) -> MemoryRecord:
        with self._cursor() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                  id, ts, memory_type, kind, content, salience, strength,
                  consolidation_state, revoked, record_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  ts = excluded.ts,
                  memory_type = excluded.memory_type,
                  kind = excluded.kind,
                  content = excluded.content,
                  salience = excluded.salience,
                  strength = excluded.strength,
                  consolidation_state = excluded.consolidation_state,
                  revoked = excluded.revoked,
                  record_json = excluded.record_json
                """,
                (
                    record.id,
                    record.ts,
                    str(record.memory_type),
                    record.kind,
                    record.content,
                    record.salience,
                    record.strength,
                    str(record.consolidation_state),
                    1 if record.revoked else 0,
                    record.model_dump_json(),
                ),
            )
        return record

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._cursor() as conn:
            row = conn.execute("SELECT record_json FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return MemoryRecord.model_validate_json(row["record_json"]) if row else None

    def update(self, record: MemoryRecord) -> MemoryRecord:
        return self.add(record)

    def delete(self, memory_id: str) -> None:
        with self._cursor() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            # Parity with LocalMemoryBackend: drop the embedding too, or it orphans
            # in the side-table forever (and is still decoded on every recall).
            conn.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))

    def all(self, *, live_only: bool = False) -> list[MemoryRecord]:
        # live_only pushes the revoked filter into SQL (uses idx_memories_revoked) so
        # the hot read paths scan only live memory, not all-history — forgotten rows
        # are kept for audit/reversibility but never re-parsed on every recall.
        query = "SELECT record_json FROM memories "
        query += "WHERE revoked = 0 " if live_only else ""
        query += "ORDER BY ts ASC"
        with self._cursor() as conn:
            rows = conn.execute(query).fetchall()
        records: list[MemoryRecord] = []
        for row in rows:
            try:
                records.append(MemoryRecord.model_validate_json(row["record_json"]))
            except ValueError as exc:  # one corrupt/partial row must not kill the whole layer
                print(f"yizhi: skipping malformed memory row: {exc}", file=sys.stderr)
        return records

    def set_embedding(self, memory_id: str, vector: list[float]) -> None:
        with self._cursor() as conn:
            conn.execute(
                "INSERT INTO memory_embeddings (memory_id, vector_json) VALUES (?, ?) "
                "ON CONFLICT(memory_id) DO UPDATE SET vector_json = excluded.vector_json",
                (memory_id, json.dumps(vector)),
            )

    def get_embeddings(self, memory_ids: list[str]) -> dict[str, list[float]]:
        if not memory_ids:
            return {}
        placeholders = ",".join("?" for _ in memory_ids)
        with self._cursor() as conn:
            rows = conn.execute(
                f"SELECT memory_id, vector_json FROM memory_embeddings WHERE memory_id IN ({placeholders})",
                memory_ids,
            ).fetchall()
        return {row["memory_id"]: json.loads(row["vector_json"]) for row in rows}


class Mem0Backend:
    """Optional backend that rents Mem0 storage/retrieval behind yizhi's schema.

    Mem0 is an optional dependency (`pip install yizhi[memory]`) and is imported
    lazily here so the deterministic v0 runtime and its tests never require it.
    yizhi keeps the governance economy; Mem0 supplies extraction, embeddings, and
    vector recall. The MemoryRecord <-> Mem0 payload mapping is the integration
    seam to flesh out next; see docs/memory-fork-strategy.md sec 6 and sec 9.
    """

    def __init__(self, config: dict | None = None) -> None:
        try:
            from mem0 import Memory  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - exercised only with extra installed
            raise ImportError(
                "Mem0Backend requires the optional 'memory' extra: pip install yizhi[memory]"
            ) from exc
        self._memory = Memory.from_config(config) if config else Memory()

    def _seam(self) -> None:  # pragma: no cover - documented seam, not yet wired
        raise NotImplementedError(
            "Mem0 <-> MemoryRecord mapping is a documented seam; see docs/memory-fork-strategy.md"
        )

    def add(self, record: MemoryRecord) -> MemoryRecord:  # pragma: no cover
        self._seam()

    def get(self, memory_id: str) -> MemoryRecord | None:  # pragma: no cover
        self._seam()

    def update(self, record: MemoryRecord) -> MemoryRecord:  # pragma: no cover
        self._seam()

    def delete(self, memory_id: str) -> None:  # pragma: no cover
        self._seam()

    def all(self) -> list[MemoryRecord]:  # pragma: no cover
        self._seam()
