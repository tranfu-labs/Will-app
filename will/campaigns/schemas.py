"""Campaign-level schemas.

This layer is deliberately separate from core WillState schemas. A campaign is
the long-horizon project harness: deterministic cursor, bounded task runs,
artifact contracts, acceptance gates, and append-only revision history.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from will.core.ids import new_id
from will.core.schemas import WillModel
from will.core.time import utc_now_iso


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    REVISING = "revising"


class StageStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class TaskRunStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"


class TaskRunKind(StrEnum):
    RESEARCH_TOPIC = "research_topic"
    DRAFT_ARTIFACT = "draft_artifact"
    RUN_ANALYSIS = "run_analysis"
    BACKTEST = "backtest"


class DeliverableVerdict(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class HumanStatus(StrEnum):
    AUTO = "auto"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class CampaignBudget(WillModel):
    """Per-campaign quotas, not a currency.

    The will's single currency is ExistenceBudget; delegation spends from it.
    These counters bound how much of the campaign's *allowance* has been used
    (task runs, revisions) and mirror worker cost for reporting."""

    max_stages: int = 8
    max_revisions: int = 8
    max_task_runs: int = 24
    max_worker_cost: float = 100.0
    max_data_refreshes: int = 0
    task_runs_used: int = 0
    revisions_used: int = 0
    worker_cost_used: float = 0.0
    data_refreshes_used: int = 0


class TaskBudget(WillModel):
    max_steps: int = 8
    max_tokens: int = 8000
    max_wall_time_seconds: int = 300
    max_tool_calls: int = 12
    max_file_writes: int = 2
    cost: float = 1.0


class NetworkPolicy(WillModel):
    allow_network_read: bool = False
    allowed_domains: list[str] = Field(default_factory=list)


class ArtifactSpec(WillModel):
    schema_name: str
    filename: str
    required_sections: list[str] = Field(default_factory=list)
    meta_filename: str | None = None


class AcceptanceGate(WillModel):
    required_artifact: bool = True
    required_schema: str
    # Extra project-specific banned substrings. Credential material is caught by
    # the built-in structural scan in validators.py regardless of this list —
    # bare keywords like "secret" false-positive on legitimate research prose.
    forbidden_patterns: list[str] = Field(default_factory=list)
    min_sections: list[str] = Field(default_factory=list)
    require_hash: bool = True
    require_sources: bool = False
    require_human_approval: bool = False


class CampaignStage(WillModel):
    id: str
    index: int
    title: str
    objective: str
    allowed_task_kinds: list[TaskRunKind]
    artifact_spec: ArtifactSpec
    acceptance_gate: AcceptanceGate
    status: StageStatus = StageStatus.PENDING
    deliverable_id: str | None = None
    # Accepted artifact's path, kept on the stage so later stages can read
    # earlier conclusions (knowledge flows within the campaign).
    artifact_path: str | None = None
    revision_notes: list[str] = Field(default_factory=list)


class Campaign(WillModel):
    id: str = Field(default_factory=lambda: new_id("campaign"))
    title: str
    vision: str
    status: CampaignStatus = CampaignStatus.ACTIVE
    stages: list[CampaignStage]
    cursor: int = 0
    budget: CampaignBudget = Field(default_factory=CampaignBudget)
    workspace_root: str
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class TaskRun(WillModel):
    id: str = Field(default_factory=lambda: new_id("taskrun"))
    ts: str = Field(default_factory=utc_now_iso)
    campaign_id: str
    stage_id: str
    kind: TaskRunKind
    instruction: str
    worker: str = "fake"
    cwd: str
    allowed_tools: list[str] = Field(default_factory=list)
    network_policy: NetworkPolicy = Field(default_factory=NetworkPolicy)
    budget: TaskBudget = Field(default_factory=TaskBudget)
    status: TaskRunStatus = TaskRunStatus.REQUESTED
    trace_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    summary: str = ""
    error: str | None = None


class Deliverable(WillModel):
    id: str = Field(default_factory=lambda: new_id("deliverable"))
    ts: str = Field(default_factory=utc_now_iso)
    campaign_id: str
    stage_id: str
    task_run_id: str
    artifact_path: str
    artifact_hash: str
    schema_name: str
    validation: dict
    verdict: DeliverableVerdict
    human_status: HumanStatus = HumanStatus.AUTO
    supersedes: str | None = None
