"""Interactive chat: the human talks to the will in a terminal REPL.

Chat is the R2 dialogue path made interactive. Each utterance is parsed with
the same channel grammar (ask/note/vision/kill goal); governance commands
apply BEFORE the step with semantic events; the words then enter `run_step`
as high-salience observations so the will digests them through recall /
thought / drives / memory like any world fact; answers are composed AFTER the
step from the will's own state (LLM opt-in, deterministic receipt fallback).

Bare text is treated as `ask` — in a chat the human expects an answer, not a
silent note. Slash commands:

- /status            deterministic state receipt (no step, no cost)
- /research <topic>  one governed read-only delegation (gate → existence
                     budget → coding-harness worker → secret scan) and print
                     the report; chat never bypasses the walls
- /quit              leave

Answering itself stays infrastructure-level (no budget burn); the step that
digests the utterance is real cognition and pays like any loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from yizhi.channels.base import InboundCommand, InboundVerb, parse_inbound
from yizhi.core.schemas import DelegationKind, DelegationTask, WillState
from yizhi.execution.delegation import (
    DelegationClient,
    build_delegation_proposal,
    execute_delegation,
)
from yizhi.engine.dialogue import (
    answer_asks,
    apply_governance,
    inbound_observations,
    is_kill_goal,
    _status_receipt,
)
from yizhi.engine.llm import load_llm
from yizhi.engine.loop import environment_from_name, run_step
from yizhi.state.snapshots import load_or_create_state
from yizhi.state.store import create_snapshot


@dataclass
class ChatIO:
    """Injectable IO so the offline suite can drive a full conversation."""

    input_fn: Callable[[str], str] = input
    output_fn: Callable[[str], None] = print
    transcript: list[str] = field(default_factory=list)

    def say(self, text: str) -> None:
        self.transcript.append(text)
        self.output_fn(text)


def _as_command(line: str) -> InboundCommand:
    """Channel grammar first; bare text becomes ASK (a chat expects answers)."""
    command = parse_inbound(line)
    if command is not None and command.verb == InboundVerb.NOTE and not line.lower().startswith("note"):
        return InboundCommand(verb=InboundVerb.ASK, arg=command.arg, raw=command.raw)
    return command


def _pick_environment(db_path: str | Path, state: WillState, campaign_id: str | None, worker: str):
    """Campaign context wins: an explicit --campaign-id, else the adopted
    campaign on the pursued goal, else the self repo."""
    cid = campaign_id
    if cid is None and state.goals:
        cid = state.goals[0].metadata.get("campaign_id")
    if cid:
        return environment_from_name(
            "campaign", db_path=db_path, campaign_id=cid, worker=worker, state=state
        )
    return environment_from_name("self")


def _run_research(
    topic: str,
    state: WillState,
    db_path: str | Path,
    io: ChatIO,
    client: DelegationClient | None,
) -> None:
    if client is None:
        from yizhi.config import load_delegation_config
        from yizhi.execution.delegation import CliHarnessDelegationClient

        client = CliHarnessDelegationClient(load_delegation_config())
    task = DelegationTask(
        kind=DelegationKind.RESEARCH_TOPIC,
        instruction=(
            f"研究并简要总结: {topic}\n"
            "输出一份要点式 Markdown 摘要(<=400字)，末尾用 `- ` 列表给出真实来源；"
            "不得编造 URL，不得输出密钥或凭证。"
        ),
        cwd="data",
        allowed_tools=["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
    )
    outcome = execute_delegation(
        build_delegation_proposal(task), client, state.budget, db_path
    )
    state.budget = outcome.budget
    create_snapshot(state, path=db_path)
    if outcome.verification is not None and outcome.verification.passed and outcome.report:
        io.say(outcome.report.output_text or outcome.report.summary)
        io.say(f"[research ok — budget {state.budget.balance:.1f}]")
    else:
        reason = (
            (outcome.report.error if outcome.report else None)
            or (outcome.record.error if outcome.record else None)
            or "delegation failed"
        )
        io.say(f"[research 未执行: {reason}]")


def _run_patch(
    instruction: str,
    state: WillState,
    db_path: str | Path,
    io: ChatIO,
    client: DelegationClient | None,
) -> None:
    from yizhi.execution.patches import propose_patch_via_delegation

    if client is None:
        from yizhi.config import load_delegation_config
        from yizhi.execution.delegation import CliHarnessDelegationClient

        client = CliHarnessDelegationClient(load_delegation_config())
    outcome, validation, artifact = propose_patch_via_delegation(
        instruction, cwd=".", client=client, budget=state.budget, db_path=db_path
    )
    state.budget = outcome.budget
    create_snapshot(state, path=db_path)
    if artifact:
        io.say(
            f"patch 已起草(未 apply): {artifact}\n"
            f"改动: {', '.join(validation['files'])} (+{validation['additions']} -{validation['deletions']})\n"
            f"审查: git apply --check {artifact}"
        )
    else:
        io.say(f"[patch 未通过: {'; '.join(validation['errors'])}]")


def run_chat(
    db_path: str | Path,
    *,
    campaign_id: str | None = None,
    worker: str = "fake",
    io: ChatIO | None = None,
    llm=None,
    delegation_client: DelegationClient | None = None,
    max_turns: int | None = None,
) -> int:
    io = io or ChatIO()
    state = load_or_create_state(db_path)
    if llm is None:
        llm = load_llm()  # None stays None when the engine is off — receipt answers
    io.say("will chat — 输入即对话；/status 状态，/research <主题> 查资料，/patch <改什么> 起草补丁，/quit 退出。")
    turns = 0
    while max_turns is None or turns < max_turns:
        try:
            line = io.input_fn("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        turns += 1
        if line in {"/quit", "/exit"}:
            break
        if line == "/status":
            io.say(_status_receipt(state))
            continue
        if line.startswith("/research"):
            topic = line[len("/research"):].strip()
            if not topic:
                io.say("用法: /research <主题>")
                continue
            _run_research(topic, state, db_path, io, delegation_client)
            continue
        if line.startswith("/patch"):
            instruction = line[len("/patch"):].strip()
            if not instruction:
                io.say("用法: /patch <要改什么>")
                continue
            _run_patch(instruction, state, db_path, io, delegation_client)
            continue

        command = _as_command(line)
        if command is None:
            continue
        if command.verb == InboundVerb.VISION or is_kill_goal(command):
            for message in apply_governance(state, [command], db_path):
                io.say(f"{message.title}\n{message.body}")
            create_snapshot(state, path=db_path)
            continue

        env = _pick_environment(db_path, state, campaign_id, worker)
        observations = inbound_observations([command], env.name)
        run_step(env, state, db_path, extra_observations=observations)
        for message in answer_asks(state, [command], llm):
            io.say(message.body)
    io.say("bye.")
    return 0
