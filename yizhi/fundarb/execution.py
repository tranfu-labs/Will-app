"""Execute deterministic FundArb experiment queues into an append-only results ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName
from yizhi.core.time import utc_now_iso
from yizhi.engine.judgment import CONCLUSIVE, judge_backtest
from yizhi.environments.arbbot import BACKTEST_SENTINEL, DEFAULT_ARBBOT_ROOT, DEFAULT_FUNDING_CACHE, ArbBotEnvironment
from yizhi.fundarb.dataset import _canonical_json
from yizhi.fundarb.experiments import DEFAULT_QUEUE
from yizhi.policy.gates import run_policy_gate

DEFAULT_RESULTS = Path(__file__).resolve().parents[2] / "data" / "funding" / "experiment_results.jsonl"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ExecuteQueueResult:
    results_path: str
    source_queue_path: str
    seen: int
    executed: int
    skipped: int
    denied: int
    failed: int
    judged: int
    promote: int
    kill: int
    iterate: int
    insufficient: int


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL in {path} at line {line_no}") from exc
    return records


def _command_hash(command: list[str]) -> str:
    return hashlib.sha256(_canonical_json(command).encode("utf-8")).hexdigest()


def result_id(source_coverage_id: str, experiment_id: str, command: list[str]) -> str:
    raw = "|".join([source_coverage_id, experiment_id, _command_hash(command)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _short(text: str, limit: int = 1200) -> str:
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _judgment_payload(metrics: dict[str, Any] | None) -> dict[str, Any] | None:
    judgment = judge_backtest(metrics)
    if judgment is None:
        return None
    return {
        "verdict": judgment.verdict.value,
        "confidence": judgment.confidence,
        "reasons": list(judgment.reasons),
        "conclusive": judgment.verdict in CONCLUSIVE,
    }


def _result_record(
    *,
    queue: dict[str, Any],
    experiment: dict[str, Any],
    rid: str,
    policy,
    action_record=None,
    verification=None,
    judgment: dict[str, Any] | None = None,
    status: str,
    error: str | None = None,
    now_iso: str | None = None,
    queue_path: Path,
) -> dict[str, Any]:
    metrics = dict(action_record.metrics or {}) if action_record is not None and action_record.metrics else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "fundarb_experiment_result",
        "result_id": rid,
        "executed_at": now_iso or utc_now_iso(),
        "source_queue_path": str(queue_path),
        "source_coverage_id": queue.get("source_coverage_id"),
        "experiment_id": experiment.get("id"),
        "experiment": {
            "priority": experiment.get("priority"),
            "symbol": experiment.get("symbol"),
            "min_net_bps": experiment.get("min_net_bps"),
            "horizon_hours": experiment.get("horizon_hours"),
            "coverage": experiment.get("coverage", {}),
        },
        "command": list(experiment.get("command", [])),
        "command_hash": _command_hash(list(experiment.get("command", []))),
        "policy": {
            "allowed": bool(policy.allowed),
            "decision": policy.decision,
            "reasons": list(policy.reasons),
        },
        "action": {
            "status": getattr(action_record, "status", "not_run"),
            "exit_code": getattr(action_record, "exit_code", None),
            "stdout": _short(getattr(action_record, "stdout", "") or ""),
            "stderr": _short(getattr(action_record, "stderr", "") or ""),
            "error": error,
        },
        "verification": (
            {
                "passed": bool(verification.passed),
                "checks": list(verification.checks),
                "summary": verification.summary,
            }
            if verification is not None
            else None
        ),
        "metrics": metrics,
        "judgment": judgment,
        "status": status,
        "safety": {
            "dry_run": True,
            "sentinel_only": True,
            "network_used": False,
            "live_used": False,
            "funding_cache_only": True,
        },
    }


def _proposal_for(experiment: dict[str, Any]) -> ActionProposal:
    return ActionProposal(
        environment=EnvironmentName.ARBBOT,
        action_class=ActionClass.FINANCIAL,
        title=f"Queued FundArb experiment {experiment.get('id', '')}",
        command=list(experiment.get("command", [])),
        description=str(experiment.get("rationale", "")),
        dry_run=True,
        experiment=True,
    )


def execute_experiment_queue(
    queue_path: Path = DEFAULT_QUEUE,
    results_path: Path = DEFAULT_RESULTS,
    *,
    arbbot_root: Path = DEFAULT_ARBBOT_ROOT,
    funding_cache: Path = DEFAULT_FUNDING_CACHE,
    max_experiments: int | None = None,
    now_iso: str | None = None,
    only_missing: bool = True,
) -> ExecuteQueueResult:
    queue_path = Path(queue_path)
    results_path = Path(results_path)
    queue = _read_json(queue_path)
    existing_ids = {str(row.get("result_id")) for row in _load_jsonl(results_path) if row.get("result_id")}
    env = ArbBotEnvironment(arbbot_root, funding_cache)

    appended: list[dict[str, Any]] = []
    counts = {
        "seen": 0,
        "executed": 0,
        "skipped": 0,
        "denied": 0,
        "failed": 0,
        "judged": 0,
        "promote": 0,
        "kill": 0,
        "iterate": 0,
        "insufficient": 0,
    }
    experiments = sorted(queue.get("experiments", []), key=lambda item: (item.get("priority", 0), item.get("id", "")))
    for experiment in experiments:
        if max_experiments is not None and counts["executed"] >= max_experiments:
            break
        counts["seen"] += 1
        command = list(experiment.get("command", []))
        rid = result_id(str(queue.get("source_coverage_id", "")), str(experiment.get("id", "")), command)
        if only_missing and rid in existing_ids:
            counts["skipped"] += 1
            continue

        proposal = _proposal_for(experiment)
        policy = run_policy_gate(proposal)
        fail_closed_error = None
        if not (len(command) >= 2 and command[0] == BACKTEST_SENTINEL and command[1] == "funding_diff"):
            fail_closed_error = "queue executor only runs yizhi:arbbot-backtest funding_diff sentinel commands"
        if fail_closed_error is not None or not policy.allowed:
            counts["denied"] += 1
            counts["executed"] += 1
            appended.append(
                _result_record(
                    queue=queue,
                    experiment=experiment,
                    rid=rid,
                    policy=policy,
                    status="denied",
                    error=fail_closed_error,
                    now_iso=now_iso,
                    queue_path=queue_path,
                )
            )
            existing_ids.add(rid)
            continue

        action_record = env.run(proposal)
        verification = env.verify(action_record)
        judgment = _judgment_payload(action_record.metrics)
        if judgment is not None:
            counts["judged"] += 1
            counts[judgment["verdict"]] += 1
        status = "succeeded" if action_record.exit_code == 0 and verification.passed else "failed"
        if status == "failed":
            counts["failed"] += 1
        counts["executed"] += 1
        appended.append(
            _result_record(
                queue=queue,
                experiment=experiment,
                rid=rid,
                policy=policy,
                action_record=action_record,
                verification=verification,
                judgment=judgment,
                status=status,
                now_iso=now_iso,
                queue_path=queue_path,
            )
        )
        existing_ids.add(rid)

    if appended:
        results_path.parent.mkdir(parents=True, exist_ok=True)
        with results_path.open("a", encoding="utf-8") as handle:
            for record in appended:
                handle.write(_canonical_json(record) + "\n")

    return ExecuteQueueResult(
        results_path=str(results_path),
        source_queue_path=str(queue_path),
        **counts,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute deterministic FundArb experiment queue.")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE), help="Input experiment queue JSON")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="Append-only output results JSONL")
    parser.add_argument("--arbbot-root", default=str(DEFAULT_ARBBOT_ROOT), help="ArbBot repository root")
    parser.add_argument("--funding-cache", default=str(DEFAULT_FUNDING_CACHE), help="Local funding cache JSON")
    parser.add_argument("--max-experiments", type=int, default=None, help="Maximum new queue items to execute")
    parser.add_argument("--rerun-existing", action="store_true", help="Append another result even when result_id exists")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute_experiment_queue(
        Path(args.queue),
        Path(args.results),
        arbbot_root=Path(args.arbbot_root),
        funding_cache=Path(args.funding_cache),
        max_experiments=args.max_experiments,
        only_missing=not args.rerun_existing,
    )
    print(
        "funding_experiment_results "
        f"seen={result.seen} executed={result.executed} skipped={result.skipped} "
        f"denied={result.denied} failed={result.failed} judged={result.judged} "
        f"promote={result.promote} kill={result.kill} iterate={result.iterate} "
        f"insufficient={result.insufficient} results={result.results_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
