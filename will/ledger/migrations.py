"""SQLite migrations for the Will append-only ledger."""

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
"""
