"""Shared schemas for the Will autonomous campaign harness."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from will.core.ids import new_id
from will.core.time import utc_now_iso


class ActionClass(StrEnum):
    INTERNAL = "internal"
    ARTIFACT = "artifact"
    NETWORK_READ = "network_read"
    EXTERNAL_WRITE = "external_write"
    FINANCIAL = "financial"
    CREDENTIAL = "credential"
    SELF_MODIFY = "self_modify"
    REPRODUCE = "reproduce"


class EnvironmentName(StrEnum):
    SELF_REPO = "self_repo"
    PI_AGENT = "pi_agent"
    CAMPAIGN = "campaign"


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class EventType(StrEnum):
    ACTION_PROPOSED = "ActionProposed"
    POLICY_GATE_PASSED = "PolicyGatePassed"
    POLICY_GATE_DENIED = "PolicyGateDenied"
    ACTION_STARTED = "ActionStarted"
    ACTION_SUCCEEDED = "ActionSucceeded"
    ACTION_FAILED = "ActionFailed"
    VERIFICATION_PASSED = "VerificationPassed"
    VERIFICATION_FAILED = "VerificationFailed"
    BUDGET_SPENT = "BudgetSpent"
    BUDGET_REPLENISHED = "BudgetReplenished"
    BUDGET_HALTED = "BudgetHalted"
    SNAPSHOT_CREATED = "SnapshotCreated"
    DELEGATION_REQUESTED = "DelegationRequested"
    DELEGATION_COMPLETED = "DelegationCompleted"
    DELEGATION_FAILED = "DelegationFailed"
    CAMPAIGN_STARTED = "CampaignStarted"
    CAMPAIGN_STAGE_STARTED = "CampaignStageStarted"
    TASKRUN_REQUESTED = "TaskRunRequested"
    TASKRUN_COMPLETED = "TaskRunCompleted"
    TASKRUN_FAILED = "TaskRunFailed"
    DELIVERABLE_PRODUCED = "DeliverableProduced"
    DELIVERABLE_ACCEPTED = "DeliverableAccepted"
    DELIVERABLE_REJECTED = "DeliverableRejected"
    DELIVERABLE_SUPERSEDED = "DeliverableSuperseded"
    ARTIFACT_PRODUCED = "ArtifactProduced"
    ARTIFACT_VALIDATED = "ArtifactValidated"
    SOUL_LENS_REVIEWED = "SoulLensReviewed"
    STAGE_DECISION_RECORDED = "StageDecisionRecorded"
    DELIVERY_PACK_PRODUCED = "DeliveryPackProduced"
    CAMPAIGN_STAGE_ADVANCED = "CampaignStageAdvanced"
    CAMPAIGN_REVISED = "CampaignRevised"
    CAMPAIGN_COMPLETED = "CampaignCompleted"
    CAMPAIGN_PAUSED = "CampaignPaused"
    CAMPAIGN_FAILED = "CampaignFailed"


class WillModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class IdentityProfile(WillModel):
    id: str = Field(default_factory=lambda: new_id("identity"))
    name: str = "Will"
    role: str = "Autonomous Campaign Harness"
    description: str = "A local-first harness that advances campaigns through governed workers, artifacts, lenses, decisions, and ledgered delivery."
    non_goals: list[str] = Field(
        default_factory=lambda: [
            "no live trading",
            "no credentials",
            "no reproduction",
            "no external mutation of campaign state, policy, budget, or ledger",
        ]
    )


class ValuePolicy(WillModel):
    id: str = Field(default_factory=lambda: new_id("value-policy"))
    allow_dry_run: bool = True
    allow_network_read: bool = False
    require_approval_for_external_write: bool = True
    forbidden_action_classes: list[ActionClass] = Field(
        default_factory=lambda: [
            ActionClass.CREDENTIAL,
            ActionClass.SELF_MODIFY,
            ActionClass.REPRODUCE,
        ]
    )
    notes: list[str] = Field(default_factory=lambda: ["financial actions must be paper or dry-run only in v0"])


class ExistenceBudget(WillModel):
    """Finite campaign/work delegation allowance controlled by Will."""

    balance: float = 100.0
    initial: float = 100.0
    halt_threshold: float = 0.0
    total_spent: float = 0.0
    total_replenished: float = 0.0
    spend_count: int = 0
    replenish_count: int = 0
    halted: bool = False


class WillState(WillModel):
    """Small governance snapshot.

    Campaign progress itself lives in campaign events and projections. This state
    only carries the durable harness identity, policy, budget, and active campaign
    references needed by CLI diagnostics and policy gates.
    """

    id: str = Field(default_factory=lambda: new_id("will-state"))
    ts: str = Field(default_factory=utc_now_iso)
    identity: IdentityProfile = Field(default_factory=IdentityProfile)
    value_policy: ValuePolicy = Field(default_factory=ValuePolicy)
    vision: str = ""
    active_campaign_ids: list[str] = Field(default_factory=list)
    budget: ExistenceBudget = Field(default_factory=ExistenceBudget)
    tick_count: int = 0


class ActionProposal(WillModel):
    id: str = Field(default_factory=lambda: new_id("proposal"))
    ts: str = Field(default_factory=utc_now_iso)
    environment: EnvironmentName
    action_class: ActionClass
    title: str
    command: list[str] = Field(default_factory=list)
    description: str = ""
    dry_run: bool = True
    requires_approval: bool = False
    experiment: bool = False  # a genuine evidence-producing probe (vs a routine check) — gates the ledger/replenishment
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyGateResult(WillModel):
    id: str = Field(default_factory=lambda: new_id("policy"))
    ts: str = Field(default_factory=utc_now_iso)
    proposal_id: str
    allowed: bool
    decision: str
    reasons: list[str] = Field(default_factory=list)


class ActionRecord(WillModel):
    id: str = Field(default_factory=lambda: new_id("action"))
    ts: str = Field(default_factory=utc_now_iso)
    proposal_id: str
    environment: EnvironmentName
    status: ActionStatus
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    # Structured action metrics (e.g. a backtest's sharpe/win/drawdown/n_entered),
    # carried first-class so deterministic judgment never re-parses stdout text.
    metrics: dict | None = None


class VerificationResult(WillModel):
    id: str = Field(default_factory=lambda: new_id("verify"))
    ts: str = Field(default_factory=utc_now_iso)
    action_record_id: str | None = None
    passed: bool
    checks: list[str] = Field(default_factory=list)
    summary: str


class DelegationKind(StrEnum):
    ANALYZE_REPO = "analyze_repo"
    RESEARCH_TOPIC = "research_topic"  # W2: read-only research; the harness returns text, never writes
    RUN_ANALYSIS = "run_analysis"      # W2: read-only analysis over local data; same no-write contract
    PROPOSE_PATCH = "propose_patch"    # R1: the harness returns a unified diff as TEXT; validated + archived here, never applied


class DelegationTask(WillModel):
    id: str = Field(default_factory=lambda: new_id("delegation"))
    ts: str = Field(default_factory=utc_now_iso)
    kind: DelegationKind
    instruction: str                                        # free-text brief; safety lives in the gate, not here
    cwd: str                                                # restricted in-repo relative path the harness may read
    allowed_tools: list[str] = Field(default_factory=list)  # read-only tool names handed to the harness
    allow_write: bool = False                               # R0 must be False; the gate denies True
    cost: float = 2.0                                       # existence-budget cost (network_read class)


class DelegationReport(WillModel):
    id: str = Field(default_factory=lambda: new_id("delegation-report"))
    ts: str = Field(default_factory=utc_now_iso)
    task_id: str
    ok: bool
    summary: str
    output_text: str = ""                               # full worker output; artifact-bearing kinds read this
    artifacts: list[str] = Field(default_factory=list)  # reserved for R1 patch artifacts; always empty in R0
    raw_output_ref: str = ""                            # archived full-transcript path (delegation-transcripts/)
    cost_spent: float = 0.0
    error: str | None = None
