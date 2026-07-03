"""Event-sourced persistence helpers for campaigns."""

from __future__ import annotations

from pathlib import Path

from yizhi.campaigns.schemas import Campaign, Deliverable, TaskRun
from yizhi.core.schemas import EventType
from yizhi.state.store import append_event, list_events


def append_campaign_event(
    db_path: str | Path,
    event_type: EventType,
    campaign_id: str,
    payload,
    *,
    aggregate_type: str = "campaign",
    aggregate_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> str:
    return append_event(
        event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id or campaign_id,
        payload=payload,
        correlation_id=correlation_id or campaign_id,
        causation_id=causation_id,
        path=db_path,
    )


def save_campaign_started(db_path: str | Path, campaign: Campaign) -> str:
    return append_campaign_event(db_path, EventType.CAMPAIGN_STARTED, campaign.id, campaign)


def save_taskrun_requested(db_path: str | Path, campaign_id: str, task: TaskRun) -> str:
    return append_campaign_event(
        db_path,
        EventType.TASKRUN_REQUESTED,
        campaign_id,
        task,
        aggregate_type="taskrun",
        aggregate_id=task.id,
    )


def campaign_events(db_path: str | Path, campaign_id: str) -> list[dict]:
    return list_events(path=db_path, correlation_id=campaign_id)


def load_campaign(db_path: str | Path, campaign_id: str) -> Campaign | None:
    campaign: Campaign | None = None
    for event in campaign_events(db_path, campaign_id):
        etype = event.get("type")
        payload = event.get("payload") or {}
        if etype == EventType.CAMPAIGN_STARTED.value:
            campaign = Campaign.model_validate(payload)
        elif campaign is None:
            continue
        elif etype in (
            EventType.CAMPAIGN_STAGE_STARTED.value,
            EventType.CAMPAIGN_STAGE_ADVANCED.value,
            EventType.CAMPAIGN_REVISED.value,
            EventType.CAMPAIGN_COMPLETED.value,
            EventType.CAMPAIGN_FAILED.value,
            EventType.CAMPAIGN_PAUSED.value,
        ) and "campaign" in payload:
            campaign = Campaign.model_validate(payload["campaign"])
        elif etype == EventType.DELIVERABLE_ACCEPTED.value:
            deliverable = Deliverable.model_validate(payload.get("deliverable"))
            for stage in campaign.stages:
                if stage.id == deliverable.stage_id:
                    stage.deliverable_id = deliverable.id
                    break
    return campaign
