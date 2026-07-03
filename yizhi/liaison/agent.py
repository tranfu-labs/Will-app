"""Liaison conversation coordinator."""

from __future__ import annotations

import json
from typing import Any

from yizhi.engine.llm import LLMClient
from yizhi.liaison.schemas import LiaisonDecision, LiaisonMessage, LiaisonPendingAction, LiaisonTurnResult
from yizhi.liaison.store import LiaisonStore
from yizhi.liaison.tools import LiaisonTools

MAX_LLM_STEPS = 3

_SYSTEM = (
    "You are yizhi's Liaison, the web-side coordination agent. You are not the Will Engine. "
    "You may inspect state through read tools and may only route low-risk note/ask messages to "
    "the will inbox. Vision, kill, and approve require a pending confirmation proposal. "
    'Return JSON only: {"action":"tool","tool":"get_state","args":{}} or '
    '{"action":"reply","reply":"..."} or {"action":"propose","proposal":{...}}.'
)


def _contains_any(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return any(n in lower for n in needles)


def _state_summary(state: dict[str, Any]) -> str:
    if not state.get("has_state"):
        return "还没有可读的 will 状态。"
    lines = []
    if state.get("vision"):
        lines.append(f"愿景：{state['vision']}")
    goal = state.get("goal_title") or "无当前目标"
    status = state.get("goal_status") or "-"
    lines.append(f"当前目标：{goal}（{status}）")
    if state.get("plan_total"):
        lines.append(
            f"计划进度：第 {min(state.get('plan_cursor', 0) + 1, state['plan_total'])}/{state['plan_total']} 步，"
            f"停滞 {state.get('plan_stall_count', 0)} 次。"
        )
    lines.append(
        f"存续预算：{state.get('budget_balance', 0):.1f}/{state.get('budget_initial', 0):.0f}，"
        f"压力 {state.get('budget_pressure', 0):.2f}。"
    )
    lines.append(f"回路计数：{state.get('loop_count', 0)}。")
    return "\n".join(lines)


def _tasks_summary(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "当前没有任务历史。"
    rows = []
    for task in tasks[:5]:
        progress = ""
        if task.get("steps_total"):
            progress = f" {task.get('steps_done', 0)}/{task['steps_total']} 步"
        rows.append(f"- {task.get('title', 'untitled')}（{task.get('status', '-')}）{progress}")
    return "任务概览：\n" + "\n".join(rows)


class LiaisonAgent:
    def __init__(self, tools: LiaisonTools, store: LiaisonStore, llm: LLMClient | None = None) -> None:
        self.tools = tools
        self.store = store
        self.llm = llm

    def handle_user_message(self, text: str, conversation_id: str = "default") -> LiaisonTurnResult:
        text = text.strip()
        human = self.store.append(
            LiaisonMessage(conversation_id=conversation_id, source="human", label="human", text=text)
        )
        if not text:
            reply = self.store.append(
                LiaisonMessage(conversation_id=conversation_id, source="liaison", label="reply", text="我收到的是空消息。")
            )
            return LiaisonTurnResult(messages=[human, reply])

        if self.llm is not None:
            result = self._try_llm_turn(text, conversation_id)
            if result is not None:
                return LiaisonTurnResult(messages=[human, *result.messages], pending_action=result.pending_action)

        result = self._deterministic_turn(text, conversation_id)
        return LiaisonTurnResult(
            messages=[human, *result.messages],
            sent_command_id=result.sent_command_id,
            pending_action=result.pending_action,
        )

    def confirm_pending(self, action_id: str, conversation_id: str = "default") -> LiaisonTurnResult:
        action = self.store.get_pending(action_id)
        if action is None:
            msg = self.store.append(
                LiaisonMessage(
                    conversation_id=conversation_id,
                    source="liaison",
                    label="error",
                    text="没有找到这张确认卡，可能已经过期或被清理。",
                )
            )
            return LiaisonTurnResult(messages=[msg])
        command = self.tools.send_to_will(
            action.verb, action.text, confirmed=True, correlation_id=action.correlation_id
        )
        action.confirmed = True
        msg = self.store.append(
            LiaisonMessage(
                conversation_id=conversation_id,
                source="liaison",
                label="submitted",
                text=f"已确认并提交给 will：{action.verb} {action.text}",
                refs=[command.id],
            )
        )
        return LiaisonTurnResult(messages=[msg], sent_command_id=command.id)

    def _deterministic_turn(self, text: str, conversation_id: str) -> LiaisonTurnResult:
        if _contains_any(text, ["进展", "状态", "progress", "status", "干到哪", "现在"]):
            state = self.tools.get_state()
            tasks = self.tools.get_tasks()
            reply = self.store.append(
                LiaisonMessage(
                    conversation_id=conversation_id,
                    source="liaison",
                    label="status",
                    text=_state_summary(state) + "\n\n" + _tasks_summary(tasks),
                    refs=["state", "tasks"],
                )
            )
            return LiaisonTurnResult(messages=[reply])
        if _contains_any(text, ["愿景", "vision", "战略"]):
            pending = LiaisonPendingAction(
                verb="vision",
                text=text,
                risk="high",
                confirmation_prompt="这会改变 will 的战略层 vision。确认后才会提交给 will。",
            )
            reply = self.store.append(
                LiaisonMessage(
                    conversation_id=conversation_id,
                    source="liaison",
                    label="confirm",
                    text=pending.confirmation_prompt,
                    pending_action=pending,
                )
            )
            return LiaisonTurnResult(messages=[reply], pending_action=pending)
        if _contains_any(text, ["放弃当前目标", "kill goal", "停止当前目标", "取消当前目标"]):
            pending = LiaisonPendingAction(
                verb="kill",
                text="goal",
                risk="high",
                confirmation_prompt="这会放弃当前 PURSUING 目标。确认后下一回路会重新生成目标。",
            )
            reply = self.store.append(
                LiaisonMessage(
                    conversation_id=conversation_id,
                    source="liaison",
                    label="confirm",
                    text=pending.confirmation_prompt,
                    pending_action=pending,
                )
            )
            return LiaisonTurnResult(messages=[reply], pending_action=pending)
        if text.endswith("?") or text.endswith("？") or _contains_any(text, ["为什么", "如何", "能否", "是否"]):
            command = self.tools.send_to_will("ask", text)
            reply = self.store.append(
                LiaisonMessage(
                    conversation_id=conversation_id,
                    source="liaison",
                    label="submitted",
                    text="已作为 ask 提交给 will；下一回路消化后，will 的回复会回到这里。",
                    refs=[command.id],
                )
            )
            return LiaisonTurnResult(messages=[reply], sent_command_id=command.id)
        command = self.tools.send_to_will("note", text)
        reply = self.store.append(
            LiaisonMessage(
                conversation_id=conversation_id,
                source="liaison",
                label="submitted",
                text="已作为 note 提交给 will；它会在下一回路作为高显著性观察被消化。",
                refs=[command.id],
            )
        )
        return LiaisonTurnResult(messages=[reply], sent_command_id=command.id)

    def _try_llm_turn(self, text: str, conversation_id: str) -> LiaisonTurnResult | None:
        transcript: list[dict[str, Any]] = [{"role": "human", "content": text}]
        observations: list[str] = []
        for _ in range(MAX_LLM_STEPS):
            try:
                raw = self.llm.complete_json(_SYSTEM, json.dumps({"text": text, "observations": observations}, ensure_ascii=False))
                decision = LiaisonDecision.model_validate(raw)
            except Exception:
                return None
            if decision.action == "tool":
                if not decision.tool:
                    return None
                try:
                    observations.append(json.dumps(self.tools.read_tool(decision.tool, decision.args), ensure_ascii=False))
                except Exception:
                    return None
                transcript.append({"role": "tool", "tool": decision.tool})
                continue
            if decision.action == "propose" and decision.proposal is not None:
                msg = self.store.append(
                    LiaisonMessage(
                        conversation_id=conversation_id,
                        source="liaison",
                        label="confirm",
                        text=decision.proposal.confirmation_prompt,
                        pending_action=decision.proposal,
                    )
                )
                return LiaisonTurnResult(messages=[msg], pending_action=decision.proposal)
            if decision.action == "reply" and decision.reply.strip():
                msg = self.store.append(
                    LiaisonMessage(
                        conversation_id=conversation_id,
                        source="liaison",
                        label="reply",
                        text=decision.reply.strip(),
                    )
                )
                return LiaisonTurnResult(messages=[msg])
        return None
