"""Channel dialogue: how human words reach the will, and how the will answers.

Three flows, each with a distinct governance rating (resident-operator-plan R2):

- utterances (note/ask/approve/kill-as-approval) become HIGH-salience
  `WorldObservation`s handed to `run_step` — the will digests them through the
  same recall/thought/drive/memory path as environment facts. Talking to yizhi
  is giving it something to perceive, not issuing an RPC.
- governance commands (`vision <text>`, `kill goal`) apply immediately, BEFORE
  the step, with a semantic event each (VISION_SET / GOAL_RETIRED): vision is
  the human-seeded strategy layer (goal genesis runs under it — the same
  legitimacy as the `run --vision` flag), and abandoning the current goal is the
  human's tactical veto; genesis then proposes the successor under the (possibly
  new) vision. Neither bypasses the loop: they change the premises the next
  loop reasons from, never its conclusions.
- answers to `ask` are composed AFTER the step so they can cite the loop that
  digested the question. Deterministic default is a structured status receipt;
  an enabled LLM upgrades it to a substantive reply grounded in the will's own
  state (vision/goal/plan/budget). Answering is infrastructure-level reporting:
  no budget burn, no policy gate, and any LLM failure degrades to the receipt.
"""

from __future__ import annotations

from pathlib import Path

from yizhi.channels.base import InboundCommand, InboundVerb, MessageKind, OutboundMessage
from yizhi.core.schemas import (
    EnvironmentName,
    EventType,
    GoalStatus,
    WillState,
    WorldObservation,
)
from yizhi.engine.budget import pressure as budget_pressure
from yizhi.state.store import append_event

# Human words are near-maximal salience for a will whose stake is human-anchored:
# they must survive encoding and be recallable when the loop deliberates.
INBOUND_SALIENCE = 0.9

_KILL_GOAL_ARGS = {"goal", "current goal", "当前目标", "目标"}


def is_kill_goal(command: InboundCommand) -> bool:
    return command.verb == InboundVerb.KILL and command.arg.strip().lower() in _KILL_GOAL_ARGS


def apply_governance(
    state: WillState, commands: list[InboundCommand], db_path: str | Path
) -> list[OutboundMessage]:
    """Apply vision/kill-goal commands to WillState with semantic events; return
    one confirmation message per applied command. Mutates `state` in place (the
    runner passes the same object into the next `run_step`)."""
    confirmations: list[OutboundMessage] = []
    for command in commands:
        if command.verb == InboundVerb.VISION and command.arg.strip():
            state.vision = command.arg.strip()
            append_event(
                EventType.VISION_SET, "will_state", state.id,
                {"vision": state.vision, "source": "channel"},
                correlation_id=command.id, path=db_path,
            )
            confirmations.append(OutboundMessage(
                kind=MessageKind.REPORT,
                title="愿景已更新",
                body=f"vision={state.vision}；goal genesis 将在其下设定后续目标（需 LLM 启用）。",
                correlation_id=command.id,
            ))
        elif is_kill_goal(command):
            goal = state.goals[0] if state.goals else None
            if goal is None or goal.status != GoalStatus.PURSUING:
                confirmations.append(OutboundMessage(
                    kind=MessageKind.REPORT, title="没有可放弃的目标",
                    body="当前没有 PURSUING 状态的目标。", correlation_id=command.id,
                ))
                continue
            goal.status = GoalStatus.ABANDONED
            append_event(
                EventType.GOAL_RETIRED, "goal", goal.id,
                {"goal_id": goal.id, "status": goal.status.value, "reason": "human_kill"},
                correlation_id=command.id, path=db_path,
            )
            confirmations.append(OutboundMessage(
                kind=MessageKind.REPORT,
                title="当前目标已放弃",
                body=f"已放弃「{goal.title}」；下一回路将重新生成目标。",
                correlation_id=command.id,
            ))
    return confirmations


def inbound_observations(
    commands: list[InboundCommand], environment: EnvironmentName | str
) -> list[WorldObservation]:
    """Utterances (everything that is not an applied governance command) as
    high-salience observations for the next `run_step`."""
    env = EnvironmentName(environment)
    observations: list[WorldObservation] = []
    for command in commands:
        if command.verb == InboundVerb.VISION or is_kill_goal(command):
            continue  # applied by apply_governance, not re-perceived
        verb = str(command.verb)  # use_enum_values: verb is already the plain string
        observations.append(WorldObservation(
            environment=env,
            source="channel_inbox",
            summary=f"human {verb}: {command.arg}".strip(),
            facts={"verb": verb, "arg": command.arg, "command_id": command.id},
            salience=INBOUND_SALIENCE,
        ))
    return observations


def _status_receipt(state: WillState) -> str:
    goal = state.goals[0] if state.goals else None
    plan = state.active_plan
    lines = [
        f"当前目标：{goal.title}（{goal.status}）" if goal else "当前没有目标。",
        (
            f"计划：第 {min(plan.cursor + 1, len(plan.steps))}/{len(plan.steps)} 步 — "
            f"{plan.steps[plan.cursor].description}"
            if plan and plan.cursor < len(plan.steps)
            else "计划：单步模式（无多步计划）。"
        ),
        f"存续预算：{state.budget.balance:.1f}/{state.budget.initial:.0f}，压力 {budget_pressure(state.budget):.2f}。",
        f"你的话已作为高显著性观察进入第 {state.loop_count} 回路。",
    ]
    if state.vision:
        lines.insert(0, f"愿景：{state.vision}")
    return "\n".join(lines)


_ANSWER_SYSTEM = (
    "You are yizhi, a governed will agent, answering your human's question over the "
    "interaction channel. Ground the answer ONLY in the state provided (vision, goal, plan, "
    "budget, the question itself). Be direct, at most 4 sentences, same language as the "
    "question. You cannot start actions from here; if asked to act, say what the next loop "
    'will consider. Respond as JSON: {"answer": "<text>"}.'
)


def answer_asks(
    state: WillState, commands: list[InboundCommand], llm=None
) -> list[OutboundMessage]:
    """One reply per `ask`, composed after the step that digested it. LLM
    (opt-in) answers from the will's own state; any failure or absence degrades
    to the deterministic status receipt."""
    replies: list[OutboundMessage] = []
    for command in commands:
        if command.verb != InboundVerb.ASK:
            continue
        body = _status_receipt(state)
        if llm is not None:
            goal = state.goals[0] if state.goals else None
            plan = state.active_plan
            context = "\n".join([
                f"vision: {state.vision or '(unset)'}",
                f"goal: {goal.title if goal else '(none)'} status={goal.status if goal else '-'}",
                f"plan: {[s.description for s in plan.steps] if plan else '(single-step)'} cursor={plan.cursor if plan else '-'}",
                f"budget: balance={state.budget.balance:.1f} pressure={budget_pressure(state.budget):.2f} halted={state.budget.halted}",
                f"question: {command.arg}",
            ])
            try:
                result = llm.complete_json(_ANSWER_SYSTEM, context)
                answer = str(result.get("answer", "")).strip()
                if answer:
                    body = answer
            except Exception:  # noqa: BLE001 - degrade to the receipt, never drop the reply
                pass
        replies.append(OutboundMessage(
            kind=MessageKind.REPORT,
            title=f"回复：{command.arg[:60]}" if command.arg else "回复",
            body=body,
            correlation_id=command.id,
        ))
    return replies
