"""Governed delegation to an external coding harness (R0).

yizhi owns the will; an external coding-harness CLI (Claude Code / Codex) is a bounded
HAND. A delegation is a NETWORK_READ-class ActionProposal: it must pass the policy gate
(read-only kinds, no write tools, in-repo cwd), spend existence budget, and be recorded
as DELEGATION_* semantic events. Write/apply is a later, separately-governed stage.

The deterministic offline suite never starts a subprocess — it injects FakeDelegationClient.
CliHarnessDelegationClient is the real, manual-gated path; its exact CLI flags must be
verified by a real-harness smoke (docs/project-status.md), not the offline gate.
See docs/resident-operator-plan.md (pillar A, R0).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from yizhi.config import DelegationConfig
from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    ActionRecord,
    ActionStatus,
    DelegationReport,
    DelegationTask,
    EnvironmentName,
    EventType,
    ExistenceBudget,
    PolicyGateResult,
    VerificationResult,
)
from yizhi.engine.budget import action_cost, can_afford, spend
from yizhi.policy.gates import DELEGATION_SENTINEL, run_policy_gate
from yizhi.state.store import append_event


@runtime_checkable
class DelegationClient(Protocol):
    def run(self, task: DelegationTask) -> DelegationReport: ...


class FakeDelegationClient:
    """Deterministic in-process client for tests and offline runs — never touches a CLI."""

    def __init__(self, ok: bool = True, summary: str = "fake harness analysis") -> None:
        self.ok = ok
        self.summary = summary
        self.called = False
        self.last_task: DelegationTask | None = None

    def run(self, task: DelegationTask) -> DelegationReport:
        self.called = True
        self.last_task = task
        return DelegationReport(
            task_id=task.id,
            ok=self.ok,
            summary=self.summary if self.ok else "fake harness failure",
            cost_spent=task.cost,
            error=None if self.ok else "harness returned a nonzero status",
        )


class CliHarnessDelegationClient:
    """Drives a real coding-harness CLI as a bounded read-only worker.

    Manual-gated: exact flags differ per harness and are NOT exercised by the offline
    suite. Read-only is enforced by (a) the policy gate upstream and (b) handing the
    harness only read tools and a restricted cwd here.
    """

    def __init__(self, config: DelegationConfig) -> None:
        self.config = config

    def _build_command(self, task: DelegationTask) -> list[str]:
        tools = task.allowed_tools or list(self.config.default_allowed_tools)
        if self.config.harness == "codex":
            # codex exec is non-interactive; tool restriction is harness-specific.
            return [self.config.command, "exec", task.instruction]
        # default: Claude Code print mode, restricted to the read-only tool set.
        return [
            self.config.command,
            "--print",
            "--allowedTools",
            ",".join(tools),
            task.instruction,
        ]

    def run(self, task: DelegationTask) -> DelegationReport:
        if not self.config.active:
            return DelegationReport(
                task_id=task.id,
                ok=False,
                summary="delegation disabled",
                error="DelegationConfig inactive (enabled/command not set)",
            )
        cwd = (Path(self.config.root) / task.cwd) if self.config.root else Path(task.cwd)
        try:
            completed = subprocess.run(
                self._build_command(task),
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
                timeout=self.config.request_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - a harness failure must not crash the loop
            return DelegationReport(task_id=task.id, ok=False, summary="harness invocation failed", error=str(exc))
        ok = completed.returncode == 0
        return DelegationReport(
            task_id=task.id,
            ok=ok,
            summary=(completed.stdout or "").strip()[:4000],
            cost_spent=task.cost,
            error=None if ok else (completed.stderr or "").strip()[:1000],
        )


def build_delegation_proposal(task: DelegationTask) -> ActionProposal:
    """Wrap a DelegationTask as a gated, read-only NETWORK_READ ActionProposal.

    The sentinel command carries the kind for structural gating; the full task rides in
    metadata for the gate's defense-in-depth checks and for execution."""
    return ActionProposal(
        environment=EnvironmentName.PI_AGENT,
        action_class=ActionClass.NETWORK_READ,
        title=f"Delegate[{task.kind}]: {task.instruction[:60]}",
        command=[DELEGATION_SENTINEL, f"kind={task.kind}"],
        description=task.instruction,
        dry_run=True,
        metadata={"delegation_task": task.model_dump()},
    )


@dataclass
class DelegationOutcome:
    gate: PolicyGateResult
    budget: ExistenceBudget
    record: ActionRecord | None
    report: DelegationReport | None
    verification: VerificationResult | None


def _forbidden_in_report(report: DelegationReport) -> bool:
    text = (report.summary + " " + (report.error or "")).lower()
    return any(p in text for p in ("apikey", "secret", "private key", "-----begin"))


def execute_delegation(
    proposal: ActionProposal,
    client: DelegationClient,
    budget: ExistenceBudget,
    db_path,
    correlation_id: str | None = None,
) -> DelegationOutcome:
    """Run one delegation through the full governance: gate → budget → run → verify,
    emitting semantic events at each step. Pure orchestration over existing primitives;
    it re-implements no gate/budget logic and writes no WillState."""
    corr = correlation_id or proposal.id

    gate = run_policy_gate(proposal)
    if not gate.allowed:
        append_event(EventType.POLICY_GATE_DENIED, "policy_gate", gate.id, gate, correlation_id=corr, path=db_path)
        record = ActionRecord(
            proposal_id=proposal.id,
            environment=EnvironmentName.PI_AGENT,
            status=ActionStatus.BLOCKED,
            command=proposal.command,
            error="; ".join(gate.reasons),
        )
        return DelegationOutcome(gate, budget, record, None, None)
    append_event(EventType.POLICY_GATE_PASSED, "policy_gate", gate.id, gate, correlation_id=corr, path=db_path)

    cost = action_cost(proposal.action_class)
    if not can_afford(budget, cost):
        append_event(
            EventType.BUDGET_HALTED, "budget", proposal.id,
            {"reason": "cannot afford delegation", "cost": cost}, correlation_id=corr, path=db_path,
        )
        record = ActionRecord(
            proposal_id=proposal.id,
            environment=EnvironmentName.PI_AGENT,
            status=ActionStatus.BLOCKED,
            command=proposal.command,
            error="insufficient existence budget",
        )
        return DelegationOutcome(gate, budget, record, None, None)
    budget = spend(budget, cost)
    append_event(
        EventType.BUDGET_SPENT, "budget", proposal.id,
        {"amount": cost, "balance": budget.balance}, correlation_id=corr, path=db_path,
    )

    task = DelegationTask.model_validate(proposal.metadata["delegation_task"])
    append_event(EventType.DELEGATION_REQUESTED, "delegation", task.id, task, correlation_id=corr, path=db_path)
    try:
        report = client.run(task)
    except Exception as exc:  # noqa: BLE001 - harness failures degrade to a FAILED report, never a crash
        report = DelegationReport(task_id=task.id, ok=False, summary="harness raised", error=str(exc))

    passed = report.ok and not _forbidden_in_report(report)
    status = ActionStatus.SUCCEEDED if passed else ActionStatus.FAILED
    record = ActionRecord(
        proposal_id=proposal.id,
        environment=EnvironmentName.PI_AGENT,
        status=status,
        command=proposal.command,
        stdout=report.summary,
        error=report.error,
        metrics=report.model_dump(),
    )
    if passed:
        append_event(EventType.DELEGATION_COMPLETED, "delegation", task.id, report, correlation_id=corr, path=db_path)
    else:
        append_event(EventType.DELEGATION_FAILED, "delegation", task.id, report, correlation_id=corr, path=db_path)
    verification = VerificationResult(
        action_record_id=record.id,
        passed=passed,
        checks=["harness_ok", "no_forbidden_content"],
        summary="Delegation report accepted." if passed else "Delegation rejected or failed.",
    )
    return DelegationOutcome(gate, budget, record, report, verification)
