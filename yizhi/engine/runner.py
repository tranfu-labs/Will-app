"""Continuous-operation driver — the thin outer `while` that lets yizhi run unattended.

yizhi already has the hard parts other agent loops bolt on: event-sourcing, a
per-loop snapshot, an ExistenceBudget halt, and a deterministic policy gate. What
it lacked was the outer loop. This module is exactly that and nothing more — it
ONLY calls `run_step` (every per-loop gate stays intact: budget burn, policy gate,
snapshot, salience encoding), reads the event log / budget to decide when to stop,
and never touches the governed internals.

Patterns ported (read the source, copied the logic — not frameworks adopted),
per docs/adr-001-build-rent-port.md:
- semantic stuck-detection over the event log (OpenHands `controller/stuck.py`),
- a budget/cost-bounded `while not done` (SWE-agent),
- catch-error → continue → bounded consecutive-failure cap (smolagents / Aider).

Determinism: with the LLM off, `run_step` is deterministic, so the whole runner is
offline-testable. Resume is free: `run_step` snapshots every loop, so a crashed run
resumes by re-loading the latest snapshot and looping again — no extra checkpointing.

Swappable seam: if control flow ever becomes a real graph (parallel sub-agents,
dynamic branching), `run_until` is the single function a LangGraph orchestrator
would replace; `run_step` (the governed cognition) would not change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from yizhi.core.schemas import EventType, WillState
from yizhi.engine.budget import COGNITION_COST, can_afford
from yizhi.engine.loop import LoopRunResult, run_step
from yizhi.environments.base import ActionEnvironment
from yizhi.state.store import list_events

# Stop reasons (deterministic control decisions — no LLM in the control plane).
STOP_MAX_STEPS = "max-steps"          # structural ceiling — ALWAYS applies, even if budget replenishes
STOP_BUDGET = "budget-depleted"       # economic — the ExistenceBudget can no longer afford to think
STOP_ERRORS = "errors"                # too many consecutive failing iterations
STOP_STUCK = "stuck"                  # semantic repetition over the event log (prefix of "stuck:<kind>")


@dataclass
class RunOutcome:
    steps: int
    stop_reason: str
    budget_balance: float
    halted: bool


def _action_key(event: dict) -> tuple:
    """A stable identity for the action a loop chose, from its ACTION_PROPOSED event.
    Keyed by the command (what actually runs), falling back to the title."""
    payload = event.get("payload", {})
    command = payload.get("command") or []
    return tuple(command) if command else (payload.get("title", ""),)


def detect_stuck(action_events: list[dict], *, window: int = 4) -> str | None:
    """Semantic stuck-detection (OpenHands heuristics) over recent ACTION_PROPOSED
    events, oldest→newest. Returns a stuck-kind string or None. Two signals:
    - repeating-action: the last `window` loops all chose the SAME action;
    - ping-pong: the last `2*window` loops alternate between exactly two actions.
    Compared by action identity, not event id — so it catches a spin even across
    different loop/event ids. This is also yizhi's frontier-exhaustion signal: once
    the (shallow) environment has no unexplored probe left, the agent necessarily
    repeats, and stopping then is correct — it stops draining budget on reconfirms."""
    keys = [_action_key(e) for e in action_events]
    if len(keys) >= window and len(set(keys[-window:])) == 1:
        return "repeating-action"
    if len(keys) >= window * 2:
        last = keys[-window * 2:]
        if len(set(last)) == 2 and all(last[i] != last[i + 1] for i in range(len(last) - 1)):
            return "ping-pong"
    return None


def _recent_actions(db_path: str | Path, *, window: int) -> list[dict]:
    """The most recent action events, bounded — a constant-size read regardless of
    total history (continuous operation must not re-scan the whole event log per step)."""
    recent = list_events(
        path=db_path,
        event_type=EventType.ACTION_PROPOSED.value,
        limit=window * 2,
        newest_first=True,
    )
    recent.reverse()  # back to chronological for the window heuristics
    return recent


def run_until(
    env: ActionEnvironment,
    state: WillState,
    db_path: str | Path,
    *,
    max_steps: int,
    max_consecutive_errors: int = 3,
    stop_on_stuck: bool = True,
    stuck_window: int = 4,
    sleep: float = 0.0,
    on_step: Callable[[int, LoopRunResult, WillState], None] | None = None,
) -> RunOutcome:
    """Loop `run_step` until a stop condition fires. `state` is mutated in place by
    `run_step` (budget/goals/loop_count) and snapshotted each loop, so passing it
    through is also the resume path. Belt-and-suspenders termination: a structural
    `max_steps` ceiling that ALWAYS applies, plus the economic budget halt and the
    semantic stuck-detector — no single condition can let an unattended run spin."""
    steps = 0
    consecutive_errors = 0
    reason = STOP_MAX_STEPS
    while steps < max_steps:
        # Economic stop: if the budget can't afford even to think, stop rather than
        # spin on cheap blocked loops. (run_step would halt internally anyway.)
        if state.budget.halted or not can_afford(state.budget, COGNITION_COST):
            reason = STOP_BUDGET
            break
        # Semantic stop: repetition/ping-pong over the recent action events.
        if stop_on_stuck:
            stuck = detect_stuck(_recent_actions(db_path, window=stuck_window), window=stuck_window)
            if stuck is not None:
                reason = f"{STOP_STUCK}:{stuck}"
                break
        try:
            result = run_step(env, state, db_path)
        except Exception:
            # One bad iteration must not kill an unattended run. run_step already
            # degrades LLM failures to the deterministic path; this catches harder
            # faults (env/IO). Bounded: too many in a row and we stop cleanly.
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                reason = STOP_ERRORS
                break
            continue
        consecutive_errors = 0
        steps += 1
        if on_step is not None:
            on_step(steps, result, state)
        if sleep > 0:
            time.sleep(sleep)
    return RunOutcome(
        steps=steps,
        stop_reason=reason,
        budget_balance=state.budget.balance,
        halted=state.budget.halted,
    )
