"""Build FundArb promotion/kill packets from experiment results."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yizhi.core.time import utc_now_iso
from yizhi.fundarb.dataset import _canonical_json, preserve_generated_at_when_stable
from yizhi.fundarb.execution import DEFAULT_RESULTS, _load_jsonl

DEFAULT_PACKET = Path(__file__).resolve().parents[2] / "data" / "funding" / "promotion_packet.json"
RULE_VERSION = "judgment-v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PacketResult:
    packet_path: str
    packet_id: str
    results: int
    symbols: int
    decisions: int


def packet_id(result_ids: list[str], rule_version: str = RULE_VERSION) -> str:
    raw = rule_version + "|" + "|".join(sorted(result_ids))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _metric(record: dict[str, Any], key: str) -> float:
    try:
        return float((record.get("metrics") or {}).get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _confidence(record: dict[str, Any]) -> float:
    try:
        return float((record.get("judgment") or {}).get("confidence", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _best(records: list[dict[str, Any]]) -> dict[str, Any]:
    return max(records, key=lambda r: (_metric(r, "total_realized_bps"), _metric(r, "sharpe_like"), _metric(r, "n_entered"), _confidence(r)))


def _decision(symbol: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    judged = [r for r in records if r.get("judgment")]
    verdicts = Counter((r.get("judgment") or {}).get("verdict", "none") for r in judged)
    promotes = [r for r in judged if (r.get("judgment") or {}).get("verdict") == "promote"]
    iterates = [r for r in judged if (r.get("judgment") or {}).get("verdict") == "iterate"]
    kills = [r for r in judged if (r.get("judgment") or {}).get("verdict") == "kill"]
    insufficient = [r for r in judged if (r.get("judgment") or {}).get("verdict") == "insufficient"]

    if promotes:
        decision = "promote"
        best = _best(promotes)
        next_action = "promote_to_out_of_sample_confirmation"
        reason = "at least one queued experiment met deterministic PROMOTE thresholds"
    elif iterates:
        decision = "iterate"
        best = _best(iterates)
        next_action = "refine_threshold_or_widen_sample"
        reason = "best queued experiment was net-positive but did not meet all promote thresholds"
    elif kills and not iterates and not promotes:
        decision = "kill" if not insufficient else "kill_or_data_requirement"
        best = _best(kills)
        next_action = "stop_this_grid_unless_new_data_regime_arrives" if decision == "kill" else "collect_more_data_or_retune_before_kill"
        reason = "sufficient-sample tested thresholds were no-edge; insufficient runs do not falsify the whole thesis"
    elif insufficient:
        decision = "insufficient"
        best = _best(insufficient)
        next_action = "collect_more_history_or_expand_data_source"
        reason = "queued experiments did not enter enough windows to support edge/no-edge conclusion"
    else:
        decision = "failed_or_denied"
        best = records[0]
        next_action = "fix_execution_or_policy_before_research_decision"
        reason = "no judged result is available"

    return {
        "symbol": symbol,
        "decision": decision,
        "reason": reason,
        "best_result_id": best.get("result_id"),
        "best_experiment_id": best.get("experiment_id"),
        "params": {
            "min_net_bps": (best.get("experiment") or {}).get("min_net_bps"),
            "horizon_hours": (best.get("experiment") or {}).get("horizon_hours"),
        },
        "metrics": best.get("metrics", {}),
        "judgment": best.get("judgment"),
        "verdicts": dict(verdicts),
        "evidence": {
            "result_ids": [r.get("result_id") for r in records if r.get("result_id")],
            "coverage": (best.get("experiment") or {}).get("coverage", {}),
        },
        "promotion_constraints": [
            "candidate research edge only; not live trading authorization",
            "requires out-of-sample or walk-forward confirmation before paper/live consideration",
        ],
        "killed_scope": "tested funding_diff thresholds/horizon/source_coverage_id only, not the symbol forever",
        "next_action": next_action,
    }


def build_promotion_packet(results_path: Path = DEFAULT_RESULTS, *, now_iso: str | None = None) -> dict[str, Any]:
    results_path = Path(results_path)
    records = _load_jsonl(results_path)
    source_ids = [str(r["result_id"]) for r in records if r.get("result_id")]
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        symbol = ((record.get("experiment") or {}).get("symbol") or (record.get("metrics") or {}).get("symbol"))
        if symbol:
            by_symbol[str(symbol)].append(record)

    verdict_counts = Counter((r.get("judgment") or {}).get("verdict", r.get("status", "unknown")) for r in records)
    decisions = [_decision(symbol, by_symbol[symbol]) for symbol in sorted(by_symbol)]
    decision_counts = Counter(d["decision"] for d in decisions)
    packet = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "fundarb_promotion_packet",
        "packet_id": packet_id(source_ids),
        "generated_at": now_iso or utc_now_iso(),
        "source_results_path": str(results_path),
        "source_coverage_id": next((r.get("source_coverage_id") for r in records if r.get("source_coverage_id")), None),
        "rule_version": RULE_VERSION,
        "summary": {
            "results": len(records),
            "symbols": len(by_symbol),
            "decisions": len(decisions),
            "promote": verdict_counts.get("promote", 0),
            "kill": verdict_counts.get("kill", 0),
            "iterate": verdict_counts.get("iterate", 0),
            "insufficient": verdict_counts.get("insufficient", 0),
            "failed": verdict_counts.get("failed", 0),
            "denied": verdict_counts.get("denied", 0),
            "decision_counts": dict(decision_counts),
        },
        "decisions": decisions,
        "safety": {
            "live_trading_authorized": False,
            "network_required": False,
            "source": "local funding cache + in-process ArbBot backtest results",
        },
    }
    return packet


def write_promotion_packet(packet: dict[str, Any], output_path: Path = DEFAULT_PACKET) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    packet = preserve_generated_at_when_stable(packet, output_path)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_and_write_packet(results_path: Path = DEFAULT_RESULTS, packet_path: Path = DEFAULT_PACKET) -> PacketResult:
    packet = build_promotion_packet(results_path)
    write_promotion_packet(packet, packet_path)
    return PacketResult(
        packet_path=str(packet_path),
        packet_id=str(packet["packet_id"]),
        results=int(packet["summary"]["results"]),
        symbols=int(packet["summary"]["symbols"]),
        decisions=int(packet["summary"]["decisions"]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build FundArb promotion/kill packet from experiment results.")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="Input experiment results JSONL")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET), help="Output promotion packet JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_and_write_packet(Path(args.results), Path(args.packet))
    print(
        "funding_promotion_packet "
        f"results={result.results} symbols={result.symbols} decisions={result.decisions} "
        f"packet_id={result.packet_id} packet={result.packet_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
