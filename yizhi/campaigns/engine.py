"""Deterministic campaign state machine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from yizhi.campaigns.schemas import (
    Campaign,
    CampaignStatus,
    Deliverable,
    DeliverableVerdict,
    HumanStatus,
    StageStatus,
    TaskRun,
    TaskRunKind,
    TaskRunStatus,
)
from yizhi.campaigns.store import append_campaign_event, save_taskrun_requested
from yizhi.campaigns.validators import validate_artifact
from yizhi.core.schemas import EventType
from yizhi.core.time import utc_now_iso


@dataclass
class CampaignTickResult:
    campaign: Campaign
    status: str
    stage_id: str | None = None
    task_run_id: str | None = None
    deliverable_id: str | None = None
    message: str = ""


def _active_stage(campaign: Campaign):
    if campaign.cursor >= len(campaign.stages):
        return None
    return campaign.stages[campaign.cursor]


def _stage_workspace(campaign: Campaign, stage_id: str) -> Path:
    return Path(campaign.workspace_root) / stage_id


def _task_workspace(campaign: Campaign, stage_id: str, task_id: str) -> Path:
    return _stage_workspace(campaign, stage_id) / task_id


def _fake_artifact(campaign: Campaign, task: TaskRun) -> tuple[str, str]:
    stage = next(s for s in campaign.stages if s.id == task.stage_id)
    stage_dir = _task_workspace(campaign, stage.id, task.id)
    stage_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = stage_dir / stage.artifact_spec.filename
    meta_path = stage_dir / (stage.artifact_spec.meta_filename or f"{artifact_path.name}.meta.json")
    revision_note = f"\n\nrevision_notes:\n" + "\n".join(f"- {n}" for n in stage.revision_notes) if stage.revision_notes else ""
    lines = [
        f"# {stage.title}",
        "",
        f"campaign: {campaign.id}",
        f"stage: {stage.id}",
        f"objective: {stage.objective}",
        "",
        "This is a deterministic W1 fake artifact. It proves the campaign harness, not real BTC research.",
        revision_note,
    ]
    artifact_path.write_text("\n".join(lines).strip() + "\n")
    meta = {
        "schema": stage.artifact_spec.schema_name,
        "title": stage.title,
        "sections": stage.artifact_spec.required_sections,
        "sources": [],
        "generated_by": "fake",
        "stage_id": stage.id,
        "task_run_id": task.id,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return str(artifact_path), str(meta_path)


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


def campaign_tick(db_path: str | Path, campaign: Campaign, *, worker: str = "fake") -> CampaignTickResult:
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
    task = TaskRun(
        campaign_id=campaign.id,
        stage_id=stage.id,
        kind=kind,
        instruction=f"{stage.title}: {stage.objective}",
        worker=worker,
        cwd=campaign.workspace_root,
        allowed_tools=[],
    )
    save_taskrun_requested(db_path, campaign.id, task)
    campaign.budget.task_runs_used += 1
    campaign.budget.worker_cost_used += task.budget.cost

    if worker != "fake":
        task.status = TaskRunStatus.DENIED
        task.error = "W1 only allows the deterministic fake worker"
        append_campaign_event(
            db_path,
            EventType.TASKRUN_FAILED,
            campaign.id,
            task,
            aggregate_type="taskrun",
            aggregate_id=task.id,
        )
        return CampaignTickResult(campaign, "task_denied", stage_id=stage.id, task_run_id=task.id, message=task.error)

    artifact_path, meta_path = _fake_artifact(campaign, task)
    task.status = TaskRunStatus.COMPLETED
    task.artifact_refs = [artifact_path, meta_path]
    task.trace_ref = f"fake:{task.id}"
    task.summary = "fake worker produced deterministic W1 artifact"
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

    if not validation["passed"]:
        stage.status = StageStatus.REJECTED
        append_campaign_event(
            db_path,
            EventType.DELIVERABLE_REJECTED,
            campaign.id,
            {"campaign": campaign.model_dump(), "deliverable": deliverable.model_dump()},
            aggregate_type="deliverable",
            aggregate_id=deliverable.id,
        )
        return CampaignTickResult(campaign, "deliverable_rejected", stage.id, task.id, deliverable.id, "; ".join(validation["errors"]))

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
    return CampaignTickResult(campaign, status, stage.id, task.id, deliverable.id, "stage accepted")


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
    campaign.updated_at = utc_now_iso()
    append_campaign_event(
        db_path,
        EventType.CAMPAIGN_REVISED,
        campaign.id,
        {"campaign": campaign.model_dump(), "stage_id": stage_id, "note": note, "cursor": campaign.cursor},
    )
    return campaign
