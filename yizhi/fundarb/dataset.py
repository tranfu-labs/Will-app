"""Append-only funding-rate dataset and coverage reporting.

This module turns the current VPS-fetched funding cache into a durable local
ledger. The cache is a replaceable snapshot; the ledger is append-only and
deduplicated by funding observation identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from yizhi.core.time import utc_now_iso

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "funding_cache.json"
DEFAULT_LEDGER = ROOT / "data" / "funding" / "ledger.jsonl"
DEFAULT_COVERAGE = ROOT / "data" / "funding" / "coverage.json"
SCHEMA_VERSION = 1
FUNDING_VENUES = ("binance", "bybit")


@dataclass(frozen=True)
class IngestResult:
    source_snapshot_id: str
    source_path: str
    records_seen: int
    records_added: int
    records_existing: int
    symbols_seen: int
    ledger_path: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _without_generated_at(data: dict[str, Any]) -> dict[str, Any]:
    stable = dict(data)
    stable.pop("generated_at", None)
    return stable


def preserve_generated_at_when_stable(data: dict[str, Any], output_path: Path) -> dict[str, Any]:
    """Keep generated artifacts idempotent when only the timestamp would change."""
    output_path = Path(output_path)
    if not output_path.exists():
        return data
    try:
        existing = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return data
    if not isinstance(existing, dict):
        return data
    if _without_generated_at(existing) != _without_generated_at(data):
        return data
    generated_at = existing.get("generated_at")
    if not isinstance(generated_at, str):
        return data
    preserved = dict(data)
    preserved["generated_at"] = generated_at
    return preserved


def cache_snapshot_id(cache: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(cache).encode("utf-8")).hexdigest()


def _record_id(symbol: str, venue: str, timestamp_ms: int, funding_rate: str, interval_hours: str) -> str:
    raw = "|".join([symbol, venue, str(timestamp_ms), funding_rate, interval_hours])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _iso_from_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).isoformat()


def _normalize_decimal(value: Any) -> str:
    try:
        return format(Decimal(str(value)), "f")
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid funding decimal {value!r}") from exc


def _iter_cache_records(cache: dict[str, Any], source_snapshot_id: str, ingested_at: str, source_path: Path) -> Iterable[dict[str, Any]]:
    symbols = cache.get("symbols", {})
    if not isinstance(symbols, dict):
        raise ValueError("funding cache must contain a symbols object")
    for symbol in sorted(symbols):
        entry = symbols[symbol]
        if not isinstance(entry, dict):
            continue
        interval_hours = _normalize_decimal(entry.get("interval_hours", 8))
        snapshot_diff = _normalize_decimal(entry.get("snapshot_diff", 0))
        for venue in FUNDING_VENUES:
            series = entry.get(venue, {})
            if not isinstance(series, dict):
                continue
            for ts_raw in sorted(series, key=lambda x: int(x)):
                timestamp_ms = int(ts_raw)
                funding_rate = _normalize_decimal(series[ts_raw])
                yield {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "funding_rate",
                    "record_id": _record_id(symbol, venue, timestamp_ms, funding_rate, interval_hours),
                    "ingested_at": ingested_at,
                    "source_snapshot_id": source_snapshot_id,
                    "source_path": str(source_path),
                    "symbol": symbol,
                    "venue": venue,
                    "timestamp_ms": timestamp_ms,
                    "observed_at": _iso_from_ms(timestamp_ms),
                    "funding_rate": funding_rate,
                    "interval_hours": interval_hours,
                    "snapshot_diff": snapshot_diff,
                }


def _existing_record_ids(ledger_path: Path) -> set[str]:
    if not ledger_path.exists():
        return set()
    ids: set[str] = set()
    for line_no, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL in {ledger_path} at line {line_no}") from exc
        record_id = record.get("record_id")
        if isinstance(record_id, str):
            ids.add(record_id)
    return ids


def ingest_cache(cache_path: Path = DEFAULT_CACHE, ledger_path: Path = DEFAULT_LEDGER, *, now_iso: str | None = None) -> IngestResult:
    cache_path = Path(cache_path)
    ledger_path = Path(ledger_path)
    cache = _read_json(cache_path)
    source_snapshot_id = cache_snapshot_id(cache)
    ingested_at = now_iso or utc_now_iso()
    existing = _existing_record_ids(ledger_path)
    records = list(_iter_cache_records(cache, source_snapshot_id, ingested_at, cache_path))
    additions = [record for record in records if record["record_id"] not in existing]
    if additions:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as handle:
            for record in additions:
                handle.write(_canonical_json(record) + "\n")
    return IngestResult(
        source_snapshot_id=source_snapshot_id,
        source_path=str(cache_path),
        records_seen=len(records),
        records_added=len(additions),
        records_existing=len(records) - len(additions),
        symbols_seen=len(cache.get("symbols", {}) if isinstance(cache.get("symbols", {}), dict) else {}),
        ledger_path=str(ledger_path),
    )


def _load_ledger(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line_no, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL in {ledger_path} at line {line_no}") from exc
    return out


def _safe_float(value: Any) -> float:
    return float(Decimal(str(value)))


def build_coverage_report(ledger_path: Path = DEFAULT_LEDGER, *, min_periods: int = 20) -> dict[str, Any]:
    ledger_path = Path(ledger_path)
    records = _load_ledger(ledger_path)
    by_symbol: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        if record.get("record_type") != "funding_rate":
            continue
        symbol = str(record["symbol"])
        venue = str(record["venue"])
        by_symbol.setdefault(symbol, {}).setdefault(venue, []).append(record)

    symbols: dict[str, Any] = {}
    eligible_symbols = 0
    for symbol in sorted(by_symbol):
        venues = by_symbol[symbol]
        venue_stats: dict[str, Any] = {}
        timestamp_sets: dict[str, set[int]] = {}
        interval_hours = None
        snapshot_diffs: list[float] = []
        for venue in FUNDING_VENUES:
            rows = sorted(venues.get(venue, []), key=lambda r: int(r["timestamp_ms"]))
            timestamps = {int(row["timestamp_ms"]) for row in rows}
            timestamp_sets[venue] = timestamps
            if rows:
                interval_hours = interval_hours or rows[-1].get("interval_hours")
                snapshot_diffs.append(_safe_float(rows[-1].get("snapshot_diff", 0)))
            venue_stats[venue] = {
                "points": len(rows),
                "start": _iso_from_ms(min(timestamps)) if timestamps else None,
                "end": _iso_from_ms(max(timestamps)) if timestamps else None,
            }
        overlap = set.intersection(*(timestamp_sets.get(venue, set()) for venue in FUNDING_VENUES))
        overlap_count = len(overlap)
        is_backtest_ready = overlap_count >= min_periods
        if is_backtest_ready:
            eligible_symbols += 1
        symbols[symbol] = {
            "venues": venue_stats,
            "interval_hours": interval_hours,
            "snapshot_diff": snapshot_diffs[-1] if snapshot_diffs else 0.0,
            "overlap_points": overlap_count,
            "overlap_start": _iso_from_ms(min(overlap)) if overlap else None,
            "overlap_end": _iso_from_ms(max(overlap)) if overlap else None,
            "backtest_ready": is_backtest_ready,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "ledger_path": str(ledger_path),
        "min_periods": min_periods,
        "records": len(records),
        "symbols": len(symbols),
        "venues": list(FUNDING_VENUES),
        "backtest_ready_symbols": eligible_symbols,
        "insufficient_symbols": len(symbols) - eligible_symbols,
        "symbol_coverage": symbols,
    }


def write_coverage_report(report: dict[str, Any], output_path: Path = DEFAULT_COVERAGE) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = preserve_generated_at_when_stable(report, output_path)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the local append-only FundArb funding dataset.")
    parser.add_argument("--cache", default=str(DEFAULT_CACHE), help="Input funding cache JSON")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER), help="Append-only output ledger JSONL")
    parser.add_argument("--coverage", default=str(DEFAULT_COVERAGE), help="Coverage report JSON")
    parser.add_argument("--min-periods", type=int, default=20, help="Minimum overlapping periods for backtest-ready coverage")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = ingest_cache(Path(args.cache), Path(args.ledger))
    report = build_coverage_report(Path(args.ledger), min_periods=args.min_periods)
    write_coverage_report(report, Path(args.coverage))
    print(
        "funding_dataset "
        f"source_snapshot_id={result.source_snapshot_id} "
        f"symbols={result.symbols_seen} seen={result.records_seen} "
        f"added={result.records_added} existing={result.records_existing} "
        f"backtest_ready={report['backtest_ready_symbols']}/{report['symbols']} "
        f"ledger={result.ledger_path} coverage={args.coverage}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
