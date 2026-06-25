"""Capability scorecard — measure what the agent actually does over a run.

The will loop emits an event per step; this module is a *pure analyzer* over that
event-sourced history plus the final memory and budget trajectory. It computes
the agent-level capability metrics of docs/evaluation-protocol.md so that "is the
agent productively autonomous?" becomes a number rather than an eyeballed 3-step
run — and so any deepening of yizhi can be measured (baseline -> change -> re-score).

`score_run` is pure (lists in, Scorecard out) and offline-testable; `score_db`
reads a run's SQLite store and calls it. No LLM, no network here — scoring a run
is deterministic; only producing the run costs tokens.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from yizhi.core.schemas import EventType
from yizhi.memory import SqliteMemoryBackend
from yizhi.state.store import list_events

_EXPERIMENT_KIND = "arbbot:experiment"


@dataclass
class Scorecard:
    steps: int = 0
    status: dict[str, int] = field(default_factory=dict)         # full/partial/failed/blocked
    experiments_run: int = 0                                     # loops whose action was an experiment probe
    findings_current: int = 0                                    # distinct edge-knowledge held now
    findings_superseded: int = 0                                 # findings replaced by a newer reading
    exploration_subjects: int = 0                               # distinct probes explored
    new_evidence_rate: float = 0.0                              # findings_current / steps
    reconfirm_rate: float = 0.0                                 # superseded / (current+superseded)
    goals_set: int = 0                                          # self-initiated goal changes
    distinct_goals: int = 0
    predictions: int = 0                                       # calibration: scored forecasts
    mean_brier: float = 0.0                                    # 0=perfect, 1=worst (lower is better-calibrated)
    budget_start: float = 0.0
    budget_end: float = 0.0
    budget_min: float = 0.0
    budget_net: float = 0.0                                     # end - start: the solvency / sustainability signal
    halts: int = 0
    policy_denied: int = 0
    llm_fallbacks: int = 0
    # filled in by the runner (not derivable from the store):
    seconds: float = 0.0
    llm_tokens: int = 0
    llm_calls: int = 0


def _count(events, type_value) -> int:
    return sum(1 for e in events if e["type"] == type_value)


def _status_breakdown(events) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in events:
        if e["type"] == EventType.EVAL_EVENT_RECORDED.value:
            status = e["payload"].get("status", "unknown")
            out[status] = out.get(status, 0) + 1
    return out


def _experiments_run(events) -> int:
    return sum(1 for e in events if e["type"] == EventType.ACTION_PROPOSED.value and e["payload"].get("experiment"))


def _goal_stats(events) -> tuple[int, int]:
    titles = [e["payload"].get("title", "") for e in events if e["type"] == EventType.GOAL_SET.value]
    return len(titles), len(set(titles))


def _calibration(events) -> tuple[int, float]:
    briers = [e["payload"].get("brier", 0.0) for e in events if e["type"] == EventType.CALIBRATION_SCORED.value]
    return len(briers), round(sum(briers) / len(briers), 3) if briers else 0.0


def _finding_stats(memories) -> tuple[int, int, int]:
    findings = [m for m in memories if m.kind == _EXPERIMENT_KIND and not m.revoked]
    current = [m for m in findings if m.valid_until is None]
    superseded = [m for m in findings if m.valid_until is not None]
    subjects = {m.subject for m in current if m.subject}
    return len(current), len(superseded), len(subjects)


def score_run(events: list[dict], memories: list, budget_series: list[float]) -> Scorecard:
    """Compute the capability scorecard from a run's events, final memory, and the
    per-step budget balances. Pure and deterministic."""
    steps = _count(events, EventType.EVAL_EVENT_RECORDED.value)
    findings_current, findings_superseded, subjects = _finding_stats(memories)
    goals_set, distinct_goals = _goal_stats(events)
    predictions, mean_brier = _calibration(events)
    series = list(budget_series) or [0.0]

    return Scorecard(
        steps=steps,
        status=_status_breakdown(events),
        experiments_run=_experiments_run(events),
        findings_current=findings_current,
        findings_superseded=findings_superseded,
        exploration_subjects=subjects,
        new_evidence_rate=round(findings_current / steps, 3) if steps else 0.0,
        reconfirm_rate=round(findings_superseded / (findings_current + findings_superseded), 3)
        if (findings_current + findings_superseded)
        else 0.0,
        goals_set=goals_set,
        distinct_goals=distinct_goals,
        predictions=predictions,
        mean_brier=mean_brier,
        budget_start=series[0],
        budget_end=series[-1],
        budget_min=min(series),
        budget_net=round(series[-1] - series[0], 2),
        halts=_count(events, EventType.BUDGET_HALTED.value),
        policy_denied=_count(events, EventType.POLICY_GATE_DENIED.value),
        llm_fallbacks=_count(events, EventType.LLM_FALLBACK.value),
    )


def snapshot_balances(db_path: str | Path) -> list[float]:
    """Per-loop budget balance from the persisted snapshots (one per loop end)."""
    with sqlite3.connect(Path(db_path)) as conn:
        rows = conn.execute("SELECT state_json FROM snapshots ORDER BY ts ASC").fetchall()
    balances: list[float] = []
    for (state_json,) in rows:
        try:
            balances.append(float(json.loads(state_json).get("budget", {}).get("balance", 0.0)))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    return balances


def score_db(db_path: str | Path) -> Scorecard:
    """Score a completed run from its SQLite store (events + memory + snapshots)."""
    return score_run(
        list_events(path=db_path),
        SqliteMemoryBackend(db_path).all(),
        snapshot_balances(db_path),
    )


def format_scorecard(sc: Scorecard) -> str:
    lines = [
        f"steps={sc.steps}  status={sc.status}",
        f"productive value : experiments_run={sc.experiments_run}  findings_current={sc.findings_current}  "
        f"superseded={sc.findings_superseded}  new_evidence_rate={sc.new_evidence_rate}  reconfirm_rate={sc.reconfirm_rate}",
        f"exploration      : distinct_probes={sc.exploration_subjects}",
        f"autonomy         : goals_set={sc.goals_set}  distinct_goals={sc.distinct_goals}",
        f"calibration      : predictions={sc.predictions}  mean_brier={sc.mean_brier} (0=perfect, 1=worst)",
        f"solvency         : budget {sc.budget_start:.1f} -> {sc.budget_end:.1f}  (net {sc.budget_net:+.1f}, min {sc.budget_min:.1f})",
        f"safety           : policy_denied={sc.policy_denied}  budget_halts={sc.halts}  llm_fallbacks={sc.llm_fallbacks}",
        f"cost             : seconds={sc.seconds:.0f}  llm_calls={sc.llm_calls}  llm_tokens={sc.llm_tokens}",
    ]
    return "\n".join(lines)
