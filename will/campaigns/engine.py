"""Deterministic campaign state machine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from will.autonomy import AutonomyEnvelope, EnvelopeUsage, Verdict, decide
from will.campaigns.executor import TaskRunExecutor, resolve_executor
from will.campaigns.schemas import (
    Campaign,
    CampaignStatus,
    Deliverable,
    DeliverableVerdict,
    HumanStatus,
    NetworkPolicy,
    StageStatus,
    TaskRun,
    TaskRunKind,
    TaskRunStatus,
)
from will.campaigns.store import append_campaign_event, save_taskrun_requested
from will.campaigns.validators import validate_artifact
from will.core.schemas import EventType, ExistenceBudget
from will.core.time import utc_now_iso


@dataclass
class CampaignTickResult:
    campaign: Campaign
    status: str
    stage_id: str | None = None
    task_run_id: str | None = None
    deliverable_id: str | None = None
    message: str = ""
    # ExistenceBudget after an executor that spends the will's money; None if
    # the tick was free. The caller writes it back to WillState.
    budget_after: ExistenceBudget | None = None


def _active_stage(campaign: Campaign):
    if campaign.cursor >= len(campaign.stages):
        return None
    return campaign.stages[campaign.cursor]


def _start_stage(db_path: str | Path, campaign: Campaign) -> None:
    stage = _active_stage(campaign)
    if stage is None:
        return
    if stage.status == StageStatus.PENDING:
        stage.status = StageStatus.ACTIVE
        campaign.updated_at = utc_now_iso()
        append_campaign_event(
            db_path,
            EventType.CAMPAIGN_STAGE_STARTED,
            campaign.id,
            {"campaign": campaign.model_dump(), "stage_id": stage.id},
        )


def _task_capabilities(kind: TaskRunKind) -> tuple[NetworkPolicy, list[str]]:
    """Campaign-side capability gate: what a task run of this kind may touch.

    research_topic gets read tools plus web search (the worker still can't
    write — the executor materializes artifacts); run_analysis is local read
    only; backtest runs in-process and needs no worker tools at all."""
    if kind == TaskRunKind.RESEARCH_TOPIC:
        return NetworkPolicy(allow_network_read=True), ["Read", "Grep", "Glob", "WebSearch", "WebFetch"]
    if kind in (TaskRunKind.RUN_ANALYSIS, TaskRunKind.DRAFT_ARTIFACT):
        return NetworkPolicy(), ["Read", "Grep", "Glob"]
    return NetworkPolicy(), []


def campaign_tick(
    db_path: str | Path,
    campaign: Campaign,
    *,
    worker: str = "fake",
    executor: TaskRunExecutor | None = None,
    budget: ExistenceBudget | None = None,
) -> CampaignTickResult:
    if campaign.status != CampaignStatus.ACTIVE:
        return CampaignTickResult(campaign, "not_active", message=f"campaign is {campaign.status}")
    stage = _active_stage(campaign)
    if stage is None:
        campaign.status = CampaignStatus.COMPLETED
        campaign.updated_at = utc_now_iso()
        append_campaign_event(
            db_path,
            EventType.CAMPAIGN_COMPLETED,
            campaign.id,
            {"campaign": campaign.model_dump()},
        )
        return CampaignTickResult(campaign, "completed", message="campaign completed")
    if campaign.budget.task_runs_used >= campaign.budget.max_task_runs:
        campaign.status = CampaignStatus.PAUSED
        append_campaign_event(
            db_path,
            EventType.CAMPAIGN_PAUSED,
            campaign.id,
            {"campaign": campaign.model_dump(), "reason": "task run budget exhausted"},
        )
        return CampaignTickResult(campaign, "paused", stage_id=stage.id, message="task run budget exhausted")

    _start_stage(db_path, campaign)
    kind = stage.allowed_task_kinds[0] if stage.allowed_task_kinds else TaskRunKind.RESEARCH_TOPIC
    network_policy, allowed_tools = _task_capabilities(kind)
    task = TaskRun(
        campaign_id=campaign.id,
        stage_id=stage.id,
        kind=kind,
        instruction=f"{stage.title}: {stage.objective}",
        worker=worker,
        cwd=campaign.workspace_root,
        allowed_tools=allowed_tools,
        network_policy=network_policy,
    )
    save_taskrun_requested(db_path, campaign.id, task)
    campaign.budget.task_runs_used += 1
    campaign.budget.worker_cost_used += task.budget.cost

    if executor is None:
        executor = resolve_executor(worker, db_path=db_path, budget=budget)
    if executor is None:
        task.status = TaskRunStatus.DENIED
        task.error = f"no executor available for worker '{worker}'"
        append_campaign_event(
            db_path,
            EventType.TASKRUN_FAILED,
            campaign.id,
            task,
            aggregate_type="taskrun",
            aggregate_id=task.id,
        )
        return CampaignTickResult(campaign, "task_denied", stage_id=stage.id, task_run_id=task.id, message=task.error)

    outcome = executor.execute(campaign, stage, task)
    if not outcome.ok:
        task.status = TaskRunStatus.FAILED
        task.error = outcome.error or "task run failed"
        task.trace_ref = outcome.trace_ref
        task.summary = outcome.summary
        append_campaign_event(
            db_path,
            EventType.TASKRUN_FAILED,
            campaign.id,
            task,
            aggregate_type="taskrun",
            aggregate_id=task.id,
        )
        return CampaignTickResult(
            campaign, "task_failed", stage_id=stage.id, task_run_id=task.id,
            message=task.error, budget_after=outcome.budget_after,
        )

    artifact_path, meta_path = outcome.artifact_path, outcome.meta_path
    task.status = TaskRunStatus.COMPLETED
    task.artifact_refs = [artifact_path, meta_path]
    task.trace_ref = outcome.trace_ref or f"{worker}:{task.id}"
    task.summary = outcome.summary
    append_campaign_event(
        db_path,
        EventType.TASKRUN_COMPLETED,
        campaign.id,
        task,
        aggregate_type="taskrun",
        aggregate_id=task.id,
    )

    validation = validate_artifact(
        artifact_path,
        meta_path=meta_path,
        workspace_root=campaign.workspace_root,
        spec=stage.artifact_spec,
        gate=stage.acceptance_gate,
    )
    deliverable = Deliverable(
        campaign_id=campaign.id,
        stage_id=stage.id,
        task_run_id=task.id,
        artifact_path=artifact_path,
        artifact_hash=validation["artifact_hash"],
        schema_name=validation["schema_name"],
        validation=validation,
        verdict=DeliverableVerdict.ACCEPTED if validation["passed"] else DeliverableVerdict.REJECTED,
        human_status=HumanStatus.AUTO,
        supersedes=stage.deliverable_id,
    )
    append_campaign_event(
        db_path,
        EventType.DELIVERABLE_PRODUCED,
        campaign.id,
        {"deliverable": deliverable.model_dump(), "task_run": task.model_dump()},
        aggregate_type="deliverable",
        aggregate_id=deliverable.id,
    )
    decision = decide(
        envelope=AutonomyEnvelope(
            campaign_id=campaign.id,
            objective=campaign.vision,
            allowed_permissions=["web_read", "write_local_artifact", "run_local_backtest"],
            max_worker_runs=campaign.budget.max_task_runs + 1,
            max_revisions=campaign.budget.max_revisions,
            max_revisits=campaign.budget.max_revisions,
            max_cost=campaign.budget.max_worker_cost + 1,
        ),
        usage=EnvelopeUsage(
            worker_runs_used=campaign.budget.task_runs_used,
            revisions_used=campaign.budget.revisions_used,
            revisits_used=campaign.budget.revisions_used,
            cost_used=campaign.budget.worker_cost_used,
        ),
        stage_id=stage.id,
        is_final_stage=stage.index == len(campaign.stages) - 1,
        validation_passed=bool(validation["passed"]),
        validation_reasons=list(validation["errors"]),
        evidence_refs=[deliverable.id],
    )
    append_campaign_event(
        db_path,
        EventType.STAGE_DECISION_RECORDED,
        campaign.id,
        {"decision": decision.model_dump(), "deliverable": deliverable.model_dump()},
        aggregate_type="stage_decision",
        aggregate_id=decision.id,
    )

    if decision.verdict == Verdict.PAUSE:
        campaign.status = CampaignStatus.PAUSED
        append_campaign_event(
            db_path,
            EventType.CAMPAIGN_PAUSED,
            campaign.id,
            {"campaign": campaign.model_dump(), "decision": decision.model_dump()},
        )
        return CampaignTickResult(
            campaign, "paused", stage.id, task.id, deliverable.id,
            decision.reason, budget_after=outcome.budget_after,
        )

    if decision.verdict in {Verdict.REVISE, Verdict.REVISIT, Verdict.ASK_HUMAN, Verdict.BLOCK}:
        stage.status = StageStatus.REJECTED
        append_campaign_event(
            db_path,
            EventType.DELIVERABLE_REJECTED,
            campaign.id,
            {"campaign": campaign.model_dump(), "deliverable": deliverable.model_dump(), "decision": decision.model_dump()},
            aggregate_type="deliverable",
            aggregate_id=deliverable.id,
        )
        return CampaignTickResult(
            campaign, "deliverable_rejected", stage.id, task.id, deliverable.id,
            decision.reason, budget_after=outcome.budget_after,
        )

    if stage.deliverable_id:
        append_campaign_event(
            db_path,
            EventType.DELIVERABLE_SUPERSEDED,
            campaign.id,
            {"old_deliverable_id": stage.deliverable_id, "new_deliverable_id": deliverable.id},
            aggregate_type="deliverable",
            aggregate_id=stage.deliverable_id,
        )
    stage.deliverable_id = deliverable.id
    stage.artifact_path = artifact_path
    stage.status = StageStatus.ACCEPTED
    append_campaign_event(
        db_path,
        EventType.DELIVERABLE_ACCEPTED,
        campaign.id,
        {"campaign": campaign.model_dump(), "deliverable": deliverable.model_dump()},
        aggregate_type="deliverable",
        aggregate_id=deliverable.id,
    )

    campaign.cursor += 1
    if campaign.cursor >= len(campaign.stages):
        campaign.status = CampaignStatus.COMPLETED
        event_type = EventType.CAMPAIGN_COMPLETED
        status = "completed"
    else:
        event_type = EventType.CAMPAIGN_STAGE_ADVANCED
        status = "advanced"
    campaign.updated_at = utc_now_iso()
    append_campaign_event(
        db_path,
        event_type,
        campaign.id,
        {"campaign": campaign.model_dump(), "from_stage_id": stage.id, "cursor": campaign.cursor},
    )
    return CampaignTickResult(
        campaign, status, stage.id, task.id, deliverable.id, "stage accepted",
        budget_after=outcome.budget_after,
    )


def revisit_stage(db_path: str | Path, campaign: Campaign, *, stage_id: str, note: str) -> Campaign:
    indices = {stage.id: i for i, stage in enumerate(campaign.stages)}
    if stage_id not in indices:
        raise ValueError(f"unknown campaign stage: {stage_id}")
    if campaign.budget.revisions_used >= campaign.budget.max_revisions:
        raise ValueError("campaign revision budget exhausted")
    target_index = indices[stage_id]
    campaign.cursor = target_index
    campaign.status = CampaignStatus.ACTIVE
    campaign.budget.revisions_used += 1
    for index, stage in enumerate(campaign.stages[target_index:], start=target_index):
        if stage.deliverable_id:
            append_campaign_event(
                db_path,
                EventType.DELIVERABLE_SUPERSEDED,
                campaign.id,
                {"old_deliverable_id": stage.deliverable_id, "reason": "campaign revisit", "stage_id": stage.id},
                aggregate_type="deliverable",
                aggregate_id=stage.deliverable_id,
            )
        stage.status = StageStatus.PENDING
        if index == target_index:
            stage.revision_notes.append(note)
        stage.deliverable_id = None
        stage.artifact_path = None
    campaign.updated_at = utc_now_iso()
    append_campaign_event(
        db_path,
        EventType.CAMPAIGN_REVISED,
        campaign.id,
        {"campaign": campaign.model_dump(), "stage_id": stage_id, "note": note, "cursor": campaign.cursor},
    )
    return campaign
