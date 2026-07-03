"""The campaign harness as an action environment (ADR-004 B1).

A campaign is the will's project-shaped world. Observing it returns stage /
deliverable / quota state; the action menu is exactly three governed
sentinels — tick (advance the frontier), revisit (rework, which must carry
evidence, not a whim), report (surface state). All three are in-process
state-machine operations (INTERNAL class); a tick's delegated worker is
separately governed inside execute_delegation with its own gate, budget spend,
and secret scan.

Money: the environment bridges the will's single currency. When a tick's
executor spends ExistenceBudget (delegation), the new balance is written back
to the WillState handed in at construction — the campaign never mints its own.
"""

from __future__ import annotations

from pathlib import Path

from yizhi.campaigns.engine import campaign_tick, revisit_stage
from yizhi.campaigns.executor import TaskRunExecutor
from yizhi.campaigns.schemas import CampaignStatus, StageStatus
from yizhi.campaigns.store import load_campaign
from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    ActionRecord,
    ActionStatus,
    EnvironmentName,
    VerificationResult,
    WillState,
    WorldObservation,
)
from yizhi.policy.gates import CAMPAIGN_SENTINEL


class CampaignEnvironment:
    name = EnvironmentName.CAMPAIGN.value

    def __init__(
        self,
        db_path: str | Path,
        campaign_id: str,
        *,
        worker: str = "fake",
        state: WillState | None = None,
        executor: TaskRunExecutor | None = None,
        root: str | Path | None = None,
    ) -> None:
        self.db_path = db_path
        self.campaign_id = campaign_id
        self.worker = worker
        self.state = state
        self.executor = executor
        self.root = Path(root) if root is not None else Path.cwd()

    def _load(self):
        return load_campaign(self.db_path, self.campaign_id)

    def observe(self) -> list[WorldObservation]:
        campaign = self._load()
        if campaign is None:
            return [
                WorldObservation(
                    environment=EnvironmentName.CAMPAIGN,
                    source="campaign.missing",
                    summary=f"Campaign {self.campaign_id} does not exist in the store.",
                    facts={"campaign_id": self.campaign_id, "exists": False},
                    salience=0.4,
                )
            ]
        active = campaign.stages[campaign.cursor] if campaign.cursor < len(campaign.stages) else None
        rejected = [s.id for s in campaign.stages if s.status == StageStatus.REJECTED]
        accepted = [s.id for s in campaign.stages if s.status == StageStatus.ACCEPTED]
        return [
            WorldObservation(
                environment=EnvironmentName.CAMPAIGN,
                source="campaign.state",
                summary=(
                    f"Campaign {campaign.id} is {campaign.status}; cursor {campaign.cursor}/"
                    f"{len(campaign.stages)}"
                    + (f"; active stage {active.id}: {active.title}" if active else "")
                    + (f"; rejected stages: {', '.join(rejected)}" if rejected else "")
                ),
                facts={
                    "campaign_id": campaign.id,
                    "exists": True,
                    "status": str(campaign.status),
                    "cursor": campaign.cursor,
                    "stages": len(campaign.stages),
                    "active_stage_id": active.id if active else None,
                    "active_stage_objective": active.objective if active else None,
                    "rejected_stage_ids": rejected,
                    "accepted_stage_ids": accepted,
                    "accepted_artifacts": {
                        s.id: s.artifact_path for s in campaign.stages if s.artifact_path
                    },
                    "task_runs_used": campaign.budget.task_runs_used,
                    "max_task_runs": campaign.budget.max_task_runs,
                    "revisions_used": campaign.budget.revisions_used,
                },
                salience=0.7 if rejected else 0.6,
            )
        ]

    def _proposal(self, op: str, *, title: str, description: str, extra: dict | None = None,
                  experiment: bool = False) -> ActionProposal:
        payload = {"op": op, "campaign_id": self.campaign_id, **(extra or {})}
        return ActionProposal(
            environment=EnvironmentName.CAMPAIGN,
            action_class=ActionClass.INTERNAL,
            title=title,
            command=[CAMPAIGN_SENTINEL, op, self.campaign_id],
            description=description,
            dry_run=True,
            experiment=experiment,
            metadata={"campaign_op": payload},
        )

    def propose_actions(self, state: WillState) -> list[ActionProposal]:
        campaign = self._load()
        proposals: list[ActionProposal] = []
        if campaign is not None and campaign.status == CampaignStatus.ACTIVE:
            rejected = [s for s in campaign.stages if s.status == StageStatus.REJECTED]
            if rejected:
                stage = rejected[0]
                # Rework rides first when a gate has rejected work: the note cites
                # the failed deliverable as evidence, so the policy gate can hold
                # the "revisit needs evidence" line structurally.
                proposals.append(
                    self._proposal(
                        "revisit",
                        title=f"Campaign revisit {stage.id}: rework rejected deliverable",
                        description=f"Stage {stage.id} deliverable was rejected; rework it against the acceptance gate.",
                        extra={
                            "stage_id": stage.id,
                            "note": f"验收未通过，按验证错误返工 {stage.id}",
                            "evidence": stage.deliverable_id or f"stage:{stage.id}:rejected",
                        },
                    )
                )
            active = campaign.stages[campaign.cursor] if campaign.cursor < len(campaign.stages) else None
            if active is not None:
                proposals.append(
                    self._proposal(
                        "tick",
                        title=f"Campaign tick: advance {active.id} {active.title}",
                        description=f"Run one governed task for stage {active.id}: {active.objective}",
                        experiment=True,  # a tick produces a deliverable + validation evidence
                    )
                )
        proposals.append(
            self._proposal(
                "report",
                title="Campaign report: surface current state",
                description="Record the campaign's current cursor, stage statuses, and quotas.",
            )
        )
        return proposals

    def run(self, proposal: ActionProposal) -> ActionRecord:
        op = proposal.metadata.get("campaign_op") or {}
        kind = op.get("op")
        campaign = self._load()
        # Second wall, environment side: structural re-checks even though the
        # policy gate already validated shape — defense in depth.
        if campaign is None:
            return self._failed(proposal, f"campaign not found: {self.campaign_id}")
        if op.get("campaign_id") != campaign.id:
            return self._failed(proposal, "campaign_op id does not match this environment")

        if kind == "tick":
            result = campaign_tick(
                self.db_path,
                campaign,
                worker=self.worker,
                executor=self.executor,
                budget=self.state.budget if self.state is not None else None,
            )
            if result.budget_after is not None and self.state is not None:
                self.state.budget = result.budget_after
            ok = result.status in {"advanced", "completed"}
            return ActionRecord(
                proposal_id=proposal.id,
                environment=EnvironmentName.CAMPAIGN,
                status=ActionStatus.SUCCEEDED if ok else ActionStatus.FAILED,
                command=proposal.command,
                stdout=result.message,
                error=None if ok else result.message,
                metrics={
                    "campaign_id": campaign.id,
                    "tick_status": result.status,
                    "stage_id": result.stage_id,
                    "task_run_id": result.task_run_id,
                    "deliverable_id": result.deliverable_id,
                    "cursor": result.campaign.cursor,
                    "campaign_status": str(result.campaign.status),
                },
            )

        if kind == "revisit":
            try:
                revisit_stage(self.db_path, campaign, stage_id=op["stage_id"], note=op["note"])
            except (KeyError, ValueError) as exc:
                return self._failed(proposal, f"revisit rejected: {exc}")
            return ActionRecord(
                proposal_id=proposal.id,
                environment=EnvironmentName.CAMPAIGN,
                status=ActionStatus.SUCCEEDED,
                command=proposal.command,
                stdout=f"revisited {op['stage_id']}: {op['note']}",
                metrics={
                    "tick_status": "revised",
                    "stage_id": op.get("stage_id"),
                    "evidence": op.get("evidence"),
                    "cursor": campaign.cursor,
                },
            )

        if kind == "report":
            return ActionRecord(
                proposal_id=proposal.id,
                environment=EnvironmentName.CAMPAIGN,
                status=ActionStatus.SUCCEEDED,
                command=proposal.command,
                stdout=f"campaign {campaign.id} status={campaign.status} cursor={campaign.cursor}",
                metrics={
                    "tick_status": "reported",
                    "cursor": campaign.cursor,
                    "campaign_status": str(campaign.status),
                },
            )

        return self._failed(proposal, f"unknown campaign op: {kind}")

    def _failed(self, proposal: ActionProposal, error: str) -> ActionRecord:
        return ActionRecord(
            proposal_id=proposal.id,
            environment=EnvironmentName.CAMPAIGN,
            status=ActionStatus.FAILED,
            command=proposal.command,
            error=error,
        )

    def verify(self, record: ActionRecord) -> VerificationResult:
        ok = record.status == ActionStatus.SUCCEEDED
        tick_status = str((record.metrics or {}).get("tick_status", ""))
        return VerificationResult(
            action_record_id=record.id,
            passed=ok,
            checks=["campaign_op_succeeded", f"tick_status:{tick_status or 'none'}"],
            summary="Campaign operation verified." if ok else f"Campaign operation failed: {record.error}",
        )
