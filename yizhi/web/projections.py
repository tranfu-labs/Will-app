"""Read-side projections for the web panel.

Pure functions from stored facts (event dicts exactly as the store returns them,
the latest WillState snapshot, raw inbox lines) to view models. No IO and no
mutation here — every view is derivable offline from fixture events, which is
what keeps the panel an observation surface rather than a second control plane.

Task history is a reconstruction: GOAL_SET/GOAL_RETIRED events bound each goal's
lifetime window, PLAN_CREATED/PLAN_REPLANNED events matched by goal_id supply
step progress, and judgments are attributed to the goal whose window contains
them. Goals visible only in the snapshot (the deterministic default goal never
emits GOAL_SET) are merged in so the offline loop still shows its task.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field

from yizhi.channels.base import InboundVerb, parse_inbound
from yizhi.channels.notify import event_to_message
from yizhi.core.schemas import EventType, GoalStatus, WillState, YizhiModel
from yizhi.engine.budget import pressure
from yizhi.liaison.schemas import LiaisonMessage


class PlanStepView(YizhiModel):
    description: str
    status: str
    is_active: bool = False


class NowView(YizhiModel):
    has_state: bool = False
    vision: str = ""
    goal_title: str = ""
    goal_status: str = ""
    goal_description: str = ""
    plan_steps: list[PlanStepView] = Field(default_factory=list)
    plan_cursor: int = 0
    plan_total: int = 0
    plan_pct: int = 0
    plan_stall_count: int = 0
    plan_revision: int = 0
    intention_title: str = ""
    intention_rationale: str = ""
    endorsed_drive: str = ""
    budget_balance: float = 0.0
    budget_initial: float = 0.0
    budget_pct: int = 0
    budget_pressure: float = 0.0
    budget_halted: bool = False
    budget_total_spent: float = 0.0
    budget_total_replenished: float = 0.0
    loop_count: int = 0
    last_surprise: float = 0.0


class TaskView(YizhiModel):
    goal_id: str
    title: str
    description: str = ""
    status: str
    started_ts: str = ""
    ended_ts: str = ""
    steps_total: int = 0
    steps_done: int = 0
    plan_revisions: int = 0
    verdicts: list[str] = Field(default_factory=list)


class ApprovalView(YizhiModel):
    correlation_id: str
    title: str
    body: str = ""
    ts: str = ""
    status: str = "pending"  # pending | submitted


class ChatMessageView(YizhiModel):
    id: str = ""
    ts: str = ""
    role: str = "human"      # human | agent
    source: str = ""
    label: str = ""          # inbound verb (note/ask/vision/kill) or outbound kind (report/alert/...)
    title: str = ""          # outbound only
    text: str = ""
    pending_action: dict[str, Any] | None = None


def project_now(state: WillState | None, events: list[dict[str, Any]]) -> NowView:
    """The 'what is the agent doing right now' card set, from the latest snapshot.

    The active intention's text lives only in events (WillState keeps just its id),
    so the newest INTENTION_ACTIVATED payload supplies title/rationale/endorsement.
    """
    if state is None:
        return NowView()
    view = NowView(
        has_state=True,
        vision=state.vision,
        budget_balance=state.budget.balance,
        budget_initial=state.budget.initial,
        budget_pct=int(round(100 * state.budget.balance / state.budget.initial)) if state.budget.initial else 0,
        budget_pressure=round(pressure(state.budget), 3),
        budget_halted=state.budget.halted,
        budget_total_spent=state.budget.total_spent,
        budget_total_replenished=state.budget.total_replenished,
        loop_count=state.loop_count,
        last_surprise=state.last_surprise,
    )
    if state.goals:
        goal = state.goals[0]
        view.goal_title = goal.title
        view.goal_status = str(goal.status)
        view.goal_description = goal.description
    plan = state.active_plan
    if plan is not None:
        view.plan_cursor = min(plan.cursor, len(plan.steps))
        view.plan_total = len(plan.steps)
        view.plan_pct = int(round(100 * view.plan_cursor / view.plan_total)) if view.plan_total else 0
        view.plan_stall_count = plan.stall_count
        view.plan_revision = plan.revision
        view.plan_steps = [
            PlanStepView(description=s.description, status=str(s.status), is_active=(i == plan.cursor))
            for i, s in enumerate(plan.steps)
        ]
    for event in reversed(events):
        if event.get("type") == EventType.INTENTION_ACTIVATED.value:
            payload = event.get("payload") or {}
            view.intention_title = str(payload.get("title", ""))
            view.intention_rationale = str(payload.get("rationale", ""))
            view.endorsed_drive = str(payload.get("endorsed_drive") or "")
            break
    return view


def _plan_progress(payload: dict[str, Any]) -> tuple[int, int]:
    steps = payload.get("steps") or []
    done = sum(1 for s in steps if isinstance(s, dict) and s.get("status") == "done")
    return len(steps), done


def project_task_history(events: list[dict[str, Any]], state: WillState | None) -> list[TaskView]:
    """Rebuild each goal's lifecycle from the event log, newest first.

    Judgment attribution is by time window (GOAL_SET ts .. GOAL_RETIRED ts) — the
    event log does not link judgments to goals directly, and a window over the
    append-only log is deterministic and testable.
    """
    tasks: dict[str, TaskView] = {}
    order: list[str] = []
    plans_by_goal: dict[str, dict[str, Any]] = {}

    for event in events:  # store order is ts ASC
        etype = event.get("type")
        payload = event.get("payload") or {}
        if etype == EventType.GOAL_SET.value:
            goal_id = str(payload.get("id") or event.get("aggregate_id"))
            tasks[goal_id] = TaskView(
                goal_id=goal_id,
                title=str(payload.get("title", "")),
                description=str(payload.get("description", "")),
                status=str(payload.get("status", GoalStatus.PURSUING.value)),
                started_ts=str(event.get("ts", "")),
            )
            order.append(goal_id)
        elif etype == EventType.GOAL_RETIRED.value:
            goal_id = str(payload.get("goal_id") or event.get("aggregate_id"))
            task = tasks.get(goal_id)
            if task is not None:
                task.status = str(payload.get("status", task.status))
                task.ended_ts = str(event.get("ts", ""))
        elif etype in (EventType.PLAN_CREATED.value, EventType.PLAN_REPLANNED.value):
            goal_id = str(payload.get("goal_id", ""))
            if goal_id:
                plans_by_goal[goal_id] = payload
                task = tasks.get(goal_id)
                if task is not None:
                    task.steps_total, task.steps_done = _plan_progress(payload)
                    task.plan_revisions = int(payload.get("revision", 0))
        elif etype == EventType.JUDGMENT_RENDERED.value:
            ts = str(event.get("ts", ""))
            verdict = str(payload.get("verdict", ""))
            for goal_id in order:
                task = tasks[goal_id]
                if task.started_ts and ts >= task.started_ts and (not task.ended_ts or ts <= task.ended_ts):
                    task.verdicts.append(verdict)
                    break

    # Snapshot merge: the deterministic default goal never emits GOAL_SET, and the
    # snapshot's plan carries fresher step progress than the PLAN_CREATED payload.
    if state is not None:
        for goal in state.goals:
            task = tasks.get(goal.id)
            if task is None:
                task = TaskView(
                    goal_id=goal.id,
                    title=goal.title,
                    description=goal.description,
                    status=str(goal.status),
                )
                tasks[goal.id] = task
                order.append(goal.id)
            else:
                task.status = str(goal.status)
        plan = state.active_plan
        if plan is not None and plan.goal_id in tasks:
            task = tasks[plan.goal_id]
            task.steps_total = len(plan.steps)
            task.steps_done = sum(1 for s in plan.steps if str(s.status) == "done")
            task.plan_revisions = plan.revision

    ordered = [tasks[goal_id] for goal_id in reversed(order)]
    ordered.sort(key=lambda t: t.status == GoalStatus.PURSUING.value, reverse=True)
    return ordered


def project_approvals(events: list[dict[str, Any]], inbox_lines: list[str]) -> list[ApprovalView]:
    """Pending approval queue: approval-request events minus inbox replies.

    `submitted` means a human verb targeting the correlation id is already in the
    inbox file — the loop may not have polled it yet, and the panel does not
    pretend otherwise.
    """
    answered: set[str] = set()
    for line in inbox_lines:
        command = parse_inbound(line)
        if command is not None and command.verb in (InboundVerb.APPROVE, InboundVerb.KILL) and command.arg:
            answered.add(command.arg.strip())

    views: list[ApprovalView] = []
    for event in events:
        message = event_to_message(event)
        if message is None or message.kind != "approval_request":
            continue
        correlation_id = str(event.get("correlation_id") or event.get("id"))
        views.append(
            ApprovalView(
                correlation_id=correlation_id,
                title=str((event.get("payload") or {}).get("title", "")) or message.title,
                body=message.body,
                ts=str(event.get("ts", "")),
                status="submitted" if correlation_id in answered else "pending",
            )
        )
    views.reverse()  # newest first
    return views


def project_chat(inbox_lines: list[str], outbox_lines: list[str], limit: int = 150) -> list[ChatMessageView]:
    """The conversation: human inbox lines and agent outbox messages merged by
    timestamp, oldest first, tail-limited. JSON inbox lines carry their own ts;
    a hand-typed plain line has none, so it sorts by parse time — acceptable for
    the manual-echo edge case the JSONL contract allows."""
    messages: list[ChatMessageView] = []
    for line in inbox_lines:
        command = parse_inbound(line)
        if command is None:
            continue
        messages.append(ChatMessageView(
            id=command.id, ts=command.ts, role="human",
            source="human", label=str(command.verb), text=command.arg or command.raw,
        ))
    for line in outbox_lines:
        try:
            payload = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        messages.append(ChatMessageView(
            id=str(payload.get("id", "")), ts=str(payload.get("ts", "")), role="agent",
            source="will", label=str(payload.get("kind", "report")),
            title=str(payload.get("title", "")), text=str(payload.get("body", "")),
        ))
    messages.sort(key=lambda m: m.ts)
    return messages[-limit:]


def project_unified_chat(
    inbox_lines: list[str],
    outbox_lines: list[str],
    liaison_messages: list[LiaisonMessage],
    limit: int = 150,
) -> list[ChatMessageView]:
    """Conversation stream across human input, Liaison replies, and will outbox.

    Human messages are taken from Liaison history when present so a message does
    not echo twice after Liaison also routes it to the will inbox. Will outbox is
    still merged because it is the authoritative return path from the will loop.
    """
    messages: list[ChatMessageView] = []
    for message in liaison_messages:
        role = "agent" if message.source == "liaison" else message.source
        messages.append(ChatMessageView(
            id=message.id,
            ts=message.ts,
            role=role,
            source=message.source,
            label=message.label or message.source,
            title=message.title,
            text=message.text,
            pending_action=message.pending_action.model_dump() if message.pending_action else None,
        ))
    if not liaison_messages:
        return project_chat(inbox_lines, outbox_lines, limit=limit)
    for line in outbox_lines:
        try:
            payload = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        messages.append(ChatMessageView(
            id=str(payload.get("id", "")),
            ts=str(payload.get("ts", "")),
            role="will",
            source="will",
            label=str(payload.get("kind", "report")),
            title=str(payload.get("title", "")),
            text=str(payload.get("body", "")),
        ))
    messages.sort(key=lambda m: m.ts)
    return messages[-limit:]


def budget_svg_points(series: list[tuple[str, float]], width: int = 600, height: int = 120) -> str:
    """Polyline points for the budget-over-snapshots curve, scaled to the viewbox.
    Server-side SVG keeps the page dependency-free; a flat series draws mid-height."""
    if not series:
        return ""
    values = [balance for _, balance in series]
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    step = width / max(len(values) - 1, 1)
    points = [
        f"{round(i * step, 1)},{round(height - (value - low) / span * (height - 10) - 5, 1)}"
        for i, value in enumerate(values)
    ]
    return " ".join(points)
