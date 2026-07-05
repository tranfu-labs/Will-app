"""Deterministic FundArb experiment queue generation."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from yizhi.core.time import utc_now_iso
from yizhi.environments.arbbot import BACKTEST_SENTINEL
from yizhi.fundarb.dataset import DEFAULT_COVERAGE, _canonical_json, preserve_generated_at_when_stable

DEFAULT_QUEUE = Path(__file__).resolve().parents[2] / "data" / "funding" / "experiment_queue.json"
DEFAULT_MIN_NET_BPS = (-1000.0, 0.0, 3.0, 5.0, 8.0)
DEFAULT_HORIZON_HOURS = (24.0,)
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class QueueResult:
    queue_path: str
    experiments: int
    symbols: int
    source_coverage_path: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def coverage_snapshot_id(coverage: dict[str, Any]) -> str:
    stable = {
        "min_periods": coverage.get("min_periods"),
        "records": coverage.get("records"),
        "symbols": coverage.get("symbols"),
        "symbol_coverage": coverage.get("symbol_coverage", {}),
    }
    return hashlib.sha256(_canonical_json(stable).encode("utf-8")).hexdigest()


def _fmt_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _experiment_id(symbol: str, min_net_bps: float, horizon_hours: float, coverage_id: str) -> str:
    raw = "|".join([coverage_id, symbol, _fmt_number(min_net_bps), _fmt_number(horizon_hours)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _parse_float_list(values: str) -> tuple[float, ...]:
    out = tuple(float(item.strip()) for item in values.split(",") if item.strip())
    if not out:
        raise ValueError("at least one numeric value is required")
    return out


def _eligible_symbols(coverage: dict[str, Any], *, min_overlap: int, max_symbols: int | None = None) -> list[tuple[str, dict[str, Any]]]:
    symbol_coverage = coverage.get("symbol_coverage", {})
    if not isinstance(symbol_coverage, dict):
        raise ValueError("coverage report must contain a symbol_coverage object")
    eligible = [
        (symbol, facts)
        for symbol, facts in symbol_coverage.items()
        if isinstance(facts, dict)
        and bool(facts.get("backtest_ready"))
        and int(facts.get("overlap_points", 0)) >= min_overlap
    ]
    eligible.sort(key=lambda item: (-abs(float(item[1].get("snapshot_diff", 0) or 0)), item[0]))
    return eligible[:max_symbols] if max_symbols is not None else eligible


def build_experiment_queue(
    coverage_path: Path = DEFAULT_COVERAGE,
    *,
    min_net_bps: Iterable[float] = DEFAULT_MIN_NET_BPS,
    horizon_hours: Iterable[float] = DEFAULT_HORIZON_HOURS,
    min_overlap: int | None = None,
    max_symbols: int | None = None,
) -> dict[str, Any]:
    coverage_path = Path(coverage_path)
    coverage = _read_json(coverage_path)
    coverage_id = coverage_snapshot_id(coverage)
    min_overlap = min_overlap if min_overlap is not None else int(coverage.get("min_periods", 20))
    thresholds = tuple(float(v) for v in min_net_bps)
    horizons = tuple(float(v) for v in horizon_hours)
    if not thresholds or not horizons:
        raise ValueError("min_net_bps and horizon_hours must not be empty")

    experiments: list[dict[str, Any]] = []
    for rank, (symbol, facts) in enumerate(_eligible_symbols(coverage, min_overlap=min_overlap, max_symbols=max_symbols), start=1):
        for threshold in thresholds:
            for horizon in horizons:
                experiments.append(
                    {
                        "id": _experiment_id(symbol, threshold, horizon, coverage_id),
                        "status": "queued",
                        "priority": rank,
                        "symbol": symbol,
                        "min_net_bps": threshold,
                        "horizon_hours": horizon,
                        "command": [
                            BACKTEST_SENTINEL,
                            "funding_diff",
                            f"symbol={symbol}",
                            f"min_net_bps={_fmt_number(threshold)}",
                            f"horizon_hours={_fmt_number(horizon)}",
                        ],
                        "coverage": {
                            "overlap_points": int(facts.get("overlap_points", 0)),
                            "overlap_start": facts.get("overlap_start"),
                            "overlap_end": facts.get("overlap_end"),
                            "snapshot_diff": float(facts.get("snapshot_diff", 0) or 0),
                        },
                        "rationale": (
                            "Run a funding-diff threshold sweep on a coverage-ready symbol; "
                            "judge decides PROMOTE/ITERATE/KILL/INSUFFICIENT after execution."
                        ),
                    }
                )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "source_coverage_path": str(coverage_path),
        "source_coverage_id": coverage_id,
        "min_overlap": min_overlap,
        "thresholds": list(thresholds),
        "horizon_hours": list(horizons),
        "symbols": len({item["symbol"] for item in experiments}),
        "experiments": experiments,
    }


def write_experiment_queue(queue: dict[str, Any], output_path: Path = DEFAULT_QUEUE) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    queue = preserve_generated_at_when_stable(queue, output_path)
    output_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_and_write_queue(
    coverage_path: Path = DEFAULT_COVERAGE,
    queue_path: Path = DEFAULT_QUEUE,
    *,
    min_net_bps: Iterable[float] = DEFAULT_MIN_NET_BPS,
    horizon_hours: Iterable[float] = DEFAULT_HORIZON_HOURS,
    min_overlap: int | None = None,
    max_symbols: int | None = None,
) -> QueueResult:
    queue = build_experiment_queue(
        coverage_path,
        min_net_bps=min_net_bps,
        horizon_hours=horizon_hours,
        min_overlap=min_overlap,
        max_symbols=max_symbols,
    )
    write_experiment_queue(queue, queue_path)
    return QueueResult(
        queue_path=str(queue_path),
        experiments=len(queue["experiments"]),
        symbols=queue["symbols"],
        source_coverage_path=str(coverage_path),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a deterministic FundArb experiment queue.")
    parser.add_argument("--coverage", default=str(DEFAULT_COVERAGE), help="Input coverage report JSON")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE), help="Output experiment queue JSON")
    parser.add_argument("--min-net-bps", default=",".join(_fmt_number(v) for v in DEFAULT_MIN_NET_BPS))
    parser.add_argument("--horizon-hours", default=",".join(_fmt_number(v) for v in DEFAULT_HORIZON_HOURS))
    parser.add_argument("--min-overlap", type=int, default=None, help="Override minimum overlapping periods")
    parser.add_argument("--max-symbols", type=int, default=None, help="Limit symbols after priority sorting")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_and_write_queue(
        Path(args.coverage),
        Path(args.queue),
        min_net_bps=_parse_float_list(args.min_net_bps),
        horizon_hours=_parse_float_list(args.horizon_hours),
        min_overlap=args.min_overlap,
        max_symbols=args.max_symbols,
    )
    print(
        "funding_experiment_queue "
        f"symbols={result.symbols} experiments={result.experiments} "
        f"coverage={result.source_coverage_path} queue={result.queue_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
