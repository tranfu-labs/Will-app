"""pi_agent: a bounded, read-only delegation environment (R0).

Implements the ActionEnvironment protocol so a coding-harness delegation flows through
the same observe/propose/run/verify shape as any other environment — but every action is
a read-only DelegationTask routed through the policy gate. The harness is the HAND, not
the will. See docs/resident-operator-plan.md (pillar A, R0).
"""

from __future__ import annotations

from pathlib import Path

from yizhi.core.schemas import (
    ActionProposal,
    ActionRecord,
    ActionStatus,
    DelegationKind,
    DelegationTask,
    EnvironmentName,
    VerificationResult,
    WillState,
    WorldObservation,
)
from yizhi.engine.delegation import (
    DelegationClient,
    FakeDelegationClient,
    _forbidden_in_report,
    build_delegation_proposal,
)


class PiAgentEnvironment:
    name = EnvironmentName.PI_AGENT.value

    def __init__(self, root: Path | str | None = None, client: DelegationClient | None = None) -> None:
        self.root = Path(root) if root is not None else Path.cwd()
        # Offline-safe default: a deterministic fake. Real runs inject CliHarnessDelegationClient.
        self.client: DelegationClient = client if client is not None else FakeDelegationClient()

    def observe(self) -> list[WorldObservation]:
        return [
            WorldObservation(
                environment=EnvironmentName.PI_AGENT,
                source="pi_agent.capability",
                summary="Read-only coding-harness delegation is available.",
                facts={"client": type(self.client).__name__, "root": str(self.root)},
                salience=0.4,
            )
        ]

    def propose_actions(self, state: WillState) -> list[ActionProposal]:
        task = DelegationTask(
            kind=DelegationKind.ANALYZE_REPO,
            instruction="Summarize the structure and risks of the fundarb funding-diff code.",
            cwd="yizhi/fundarb",
            allowed_tools=["Read", "Grep", "Glob"],
        )
        return [build_delegation_proposal(task)]

    def run(self, proposal: ActionProposal) -> ActionRecord:
        task = DelegationTask.model_validate(proposal.metadata["delegation_task"])
        report = self.client.run(task)
        passed = report.ok and not _forbidden_in_report(report)
        status = ActionStatus.SUCCEEDED if passed else ActionStatus.FAILED
        return ActionRecord(
            proposal_id=proposal.id,
            environment=EnvironmentName.PI_AGENT,
            status=status,
            command=proposal.command,
            stdout=report.summary,
            error=report.error if not report.ok else ("report contains forbidden content" if not passed else None),
            metrics=report.model_dump(),
        )

    def verify(self, record: ActionRecord) -> VerificationResult:
        passed = record.status == ActionStatus.SUCCEEDED
        checks = ["delegation_status_succeeded"]
        if passed:
            checks.append("no_forbidden_content")
        return VerificationResult(
            action_record_id=record.id,
            passed=passed,
            checks=checks,
            summary="Delegation succeeded." if passed else "Delegation failed or contained forbidden content.",
        )
