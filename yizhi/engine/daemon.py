"""Resident daemon (R3; resident-operator-plan pillar C, ADR-004 D4).

The will lives as a long-running process. Each tick runs a bounded burst of
governed steps via `run_until` — which itself drains the channel inbox, so
human words (vision / kill goal / notes / asks) wake and steer the will —
then pushes the burst's reportable events to the channel incrementally
(rowid cursor; nothing is re-sent), then sleeps.

Budget halted is a LOW-POWER WAIT, not an exit: notify once, keep draining
the channel (a human may re-vision or intervene), never auto-refill — the
failure direction stays safe. Nothing here adds permissions or bypasses a
gate; the daemon only replaces the human's enter key with a clock.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from yizhi.channels.base import Channel, MessageKind, OutboundMessage
from yizhi.channels.notify import event_to_message
from yizhi.core.schemas import WillState
from yizhi.engine.dialogue import apply_governance, answer_asks, inbound_observations
from yizhi.engine.runner import run_until
from yizhi.environments.base import ActionEnvironment
from yizhi.state.store import create_snapshot, list_events


@dataclass
class ResidentOutcome:
    ticks: int
    steps: int
    stop_reason: str  # "max_ticks" | "interrupted"


def _latest_rowid(db_path: str | Path) -> int:
    events = list_events(path=db_path, limit=1, newest_first=True)
    return int(events[0].get("rowid", 0)) if events else 0


def _report_new_events(db_path: str | Path, channel: Channel, cursor: int) -> int:
    """Push reportable events appended after `cursor`; return the new cursor.
    Reporting is infrastructure-level — no budget, no gate."""
    for event in list_events(path=db_path, after_rowid=cursor):
        cursor = max(cursor, int(event.get("rowid", cursor)))
        message = event_to_message(event)
        if message is not None:
            channel.send(message)
    return cursor


def _halted_tick(state: WillState, db_path: str | Path, channel: Channel) -> None:
    """Low-power wait: drain the channel so governance still works, answer asks
    from state, but run no steps and spend nothing."""
    commands = channel.poll()
    if not commands:
        return
    for message in apply_governance(state, commands, db_path):
        channel.send(message)
    # Utterances are acknowledged from state (no loop to digest them while halted).
    for message in answer_asks(state, commands):
        channel.send(message)
    if inbound_observations(commands, "self_repo"):
        create_snapshot(state, path=db_path)


def run_resident(
    env: ActionEnvironment,
    state: WillState,
    db_path: str | Path,
    *,
    channel: Channel,
    tick_interval: float = 60.0,
    max_steps_per_tick: int = 3,
    max_ticks: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    on_tick: Callable[[int, WillState], None] | None = None,
) -> ResidentOutcome:
    """Long-lived residency over the existing bounded runner. `max_ticks=None`
    runs until interrupted (systemd/tmux territory); tests and smokes pass a
    bound. Every governance property of `run_until` (budget halt, stuck stop,
    snapshot resume, channel drain) applies unchanged within each tick."""
    cursor = _latest_rowid(db_path)
    halted_notified = False
    ticks = 0
    steps = 0
    try:
        while max_ticks is None or ticks < max_ticks:
            ticks += 1
            if state.budget.halted:
                if not halted_notified:
                    channel.send(OutboundMessage(
                        kind=MessageKind.ALERT,
                        title="存在预算耗尽——低功耗等待",
                        body=(
                            f"balance={state.budget.balance:.1f}; 我停止行动但仍在听渠道。"
                            "人工介入(新 vision / 外部价值)之前不会自动续命。"
                        ),
                    ))
                    halted_notified = True
                _halted_tick(state, db_path, channel)
            else:
                halted_notified = False
                outcome = run_until(
                    env,
                    state,
                    db_path,
                    max_steps=max_steps_per_tick,
                    channel=channel,
                )
                steps += outcome.steps
            cursor = _report_new_events(db_path, channel, cursor)
            if on_tick is not None:
                on_tick(ticks, state)
            if max_ticks is None or ticks < max_ticks:
                sleep_fn(tick_interval)
    except KeyboardInterrupt:
        return ResidentOutcome(ticks=ticks, steps=steps, stop_reason="interrupted")
    return ResidentOutcome(ticks=ticks, steps=steps, stop_reason="max_ticks")
