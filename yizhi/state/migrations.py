"""SQLite migrations for the v0 event store."""

from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events(
  id text primary key,
  ts text not null,
  type text not null,
  aggregate_type text not null,
  aggregate_id text not null,
  payload_json text not null,
  causation_id text,
  correlation_id text,
  status text not null default 'committed'
);

CREATE INDEX IF NOT EXISTS idx_events_correlation_id ON events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_events_aggregate_id ON events(aggregate_id);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS snapshots(
  id text primary key,
  ts text not null,
  state_json text not null
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);

CREATE TABLE IF NOT EXISTS memories(
  id text primary key,
  ts text not null,
  memory_type text not null,
  kind text not null,
  content text not null,
  salience real not null,
  strength real not null,
  consolidation_state text not null,
  revoked integer not null default 0,
  record_json text not null
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_revoked ON memories(revoked);

CREATE TABLE IF NOT EXISTS memory_embeddings(
  memory_id text primary key,
  vector_json text not null
);
"""
