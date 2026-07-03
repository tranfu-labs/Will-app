"""Public v0 schemas for the governed will loop."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from yizhi.core.ids import new_id
from yizhi.core.time import utc_now_iso


class ActionClass(StrEnum):
    INTERNAL = "internal"
    MEMORY = "memory"
    ARTIFACT = "artifact"
    NETWORK_READ = "network_read"
    EXTERNAL_WRITE = "external_write"
    FINANCIAL = "financial"
    CREDENTIAL = "credential"
    SELF_MODIFY = "self_modify"
    REPRODUCE = "reproduce"


class EnvironmentName(StrEnum):
    SELF_REPO = "self_repo"
    ARBBOT = "arbbot"
    PI_AGENT = "pi_agent"


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class LoopStatus(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    REFLECTIVE = "reflective"
    IDENTITY = "identity"
    POLICY = "policy"
    CALIBRATION = "calibration"  # metamemory: the agent's own reliability/track-record
    PROSPECTIVE = "prospective"  # remembering to act later, at a time or condition cue


class MemorySource(StrEnum):
    OBSERVED = "observed"    # read from the world / a deterministic artifact
    INFERRED = "inferred"    # the agent's own synthesis (a reflection, a hypothesis)
    TOLD = "told"            # asserted by a human or external source


class ConsolidationState(StrEnum):
    RAW = "raw"
    CONSOLIDATED = "consolidated"
    SUMMARIZED = "summarized"


class EventType(StrEnum):
    OBSERVATION_RECORDED = "ObservationRecorded"
    THOUGHT_EVENT_GENERATED = "ThoughtEventGenerated"
    DRIVE_SIGNAL_UPDATED = "DriveSignalUpdated"
    INTENTION_PROPOSED = "IntentionProposed"
    INTENTION_ACTIVATED = "IntentionActivated"
    PLAN_CREATED = "PlanCreated"
    ACTION_PROPOSED = "ActionProposed"
    POLICY_GATE_PASSED = "PolicyGatePassed"
    POLICY_GATE_DENIED = "PolicyGateDenied"
    ACTION_STARTED = "ActionStarted"
    ACTION_SUCCEEDED = "ActionSucceeded"
    ACTION_FAILED = "ActionFailed"
    VERIFICATION_PASSED = "VerificationPassed"
    VERIFICATION_FAILED = "VerificationFailed"
    REFLECTION_CREATED = "ReflectionCreated"
    MEMORY_CREATED = "MemoryCreated"
    MEMORY_REVOKED = "MemoryRevoked"
    MEMORY_REINFORCED = "MemoryReinforced"
    MEMORY_CONSOLIDATED = "MemoryConsolidated"
    MEMORY_SUPERSEDED = "MemorySuperseded"
    MEMORY_FORGOTTEN = "MemoryForgotten"
    BUDGET_SPENT = "BudgetSpent"
    BUDGET_REPLENISHED = "BudgetReplenished"
    BUDGET_HALTED = "BudgetHalted"
    LLM_FALLBACK = "LlmFallback"
    GOAL_SET = "GoalSet"
    GOAL_RETIRED = "GoalRetired"
    VISION_SET = "VisionSet"
    CALIBRATION_SCORED = "CalibrationScored"
    SKILL_CREATED = "SkillCreated"
    EVAL_EVENT_RECORDED = "EvalEventRecorded"
    SNAPSHOT_CREATED = "SnapshotCreated"
    PLAN_STEP_ADVANCED = "PlanStepAdvanced"
    PLAN_REPLANNED = "PlanReplanned"
    CRITIQUE_RAISED = "CritiqueRaised"
    HYPOTHESIS_AUTHORED = "HypothesisAuthored"
    JUDGMENT_RENDERED = "JudgmentRendered"
    DATA_REQUESTED = "DataRequested"
    ROLLBACK_REQUESTED = "RollbackRequested"
    ROLLBACK_COMPLETED = "RollbackCompleted"
    INTENTION_RETIRED = "IntentionRetired"
    ACTION_ROLLBACK_REQUESTED = "ActionRollbackRequested"
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
    CAMPAIGN_STAGE_ADVANCED = "CampaignStageAdvanced"
    CAMPAIGN_REVISED = "CampaignRevised"
    CAMPAIGN_COMPLETED = "CampaignCompleted"
    CAMPAIGN_PAUSED = "CampaignPaused"
    CAMPAIGN_FAILED = "CampaignFailed"


class YizhiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class IdentityProfile(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("identity"))
    name: str = "Will"
    role: str = "local governed will agent"
    description: str = "A local-first agent that forms governed intentions and learns from verified action."
    non_goals: list[str] = Field(
        default_factory=lambda: [
            "no live trading",
            "no credentials",
            "no reproduction",
            "no silent core memory mutation",
        ]
    )


class ValuePolicy(YizhiModel):
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


class GoalStatus(StrEnum):
    PURSUING = "pursuing"     # currently focused and being advanced (the default)
    DONE = "done"             # completion criterion met: its plan ran to COMPLETED, or a
    # single-step goal produced verified value
    ABANDONED = "abandoned"   # replan exhausted while still stalling — give up, allow the next goal


class Goal(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("goal"))
    title: str
    description: str = ""
    priority: int = 50
    active: bool = True
    # Goal lifecycle: a goal is PURSUED to done/abandoned before genesis sets the next one, so the
    # will persistently advances ONE task across loops instead of overwriting it every loop.
    status: GoalStatus = GoalStatus.PURSUING


class ExistenceBudget(YizhiModel):
    """The agent's stake, made into a runtime object (theory-of-will.md Axiom Nine).

    A finite, renewable viability resource: acting and thinking consume it, and only
    externally verified value replenishes it. At or below `halt_threshold` the agent
    must stop acting — the failure mode points in the safe direction (a depleted
    agent halts, it does not grab). Budget pressure is what makes drives and salience
    grounded rather than stipulated.
    """

    balance: float = 100.0
    initial: float = 100.0
    halt_threshold: float = 0.0
    total_spent: float = 0.0
    total_replenished: float = 0.0
    spend_count: int = 0
    replenish_count: int = 0
    halted: bool = False


class WillState(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("will-state"))
    ts: str = Field(default_factory=utc_now_iso)
    identity: IdentityProfile = Field(default_factory=IdentityProfile)
    value_policy: ValuePolicy = Field(default_factory=ValuePolicy)
    vision: str = ""  # the stable north-star purpose (human-seeded); goal-genesis sets goals under it
    goals: list[Goal] = Field(
        default_factory=lambda: [
            Goal(
                title="Run governed autonomous value loops",
                description="Observe, think, intend, act safely, verify, reflect, and preserve rollback evidence.",
                priority=90,
            )
        ]
    )
    active_intention_id: str | None = None
    active_plan: "Plan | None" = None   # the in-flight multi-loop plan (None => single-step behavior)
    memory_ids: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    budget: ExistenceBudget = Field(default_factory=ExistenceBudget)
    loop_count: int = 0
    # Carryover of the last finding's surprise (world-model prediction error vs the prior belief
    # about its subject). It raises how strongly the NEXT loop encodes what it observes — arousal
    # enhances encoding (McGaugh; docs/theory-of-memory.md sec 2.2).
    last_surprise: float = Field(default=0.0, ge=0.0, le=1.0)
    # Homeostatic drive tensions carried across loops: an unresolved pressure (a commitment never
    # closed, a gap never explored) decays slowly and re-accumulates instead of resetting every
    # step. Keyed by drive name. See engine/drives.py.
    drive_state: dict[str, float] = Field(default_factory=dict)


class WorldObservation(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("obs"))
    ts: str = Field(default_factory=utc_now_iso)
    environment: EnvironmentName
    source: str
    summary: str
    facts: dict[str, Any] = Field(default_factory=dict)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)


class ThoughtEvent(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("thought"))
    ts: str = Field(default_factory=utc_now_iso)
    kind: str
    content: str
    source_observation_ids: list[str] = Field(default_factory=list)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)


class DriveSignal(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("drive"))
    ts: str = Field(default_factory=utc_now_iso)
    name: str
    intensity: float = Field(ge=0.0, le=1.0)
    reason: str
    source_thought_ids: list[str] = Field(default_factory=list)


class MemoryRecord(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("memory"))
    ts: str = Field(default_factory=utc_now_iso)
    kind: str
    content: str
    source_event_ids: list[str] = Field(default_factory=list)
    revoked: bool = False
    revoke_reason: str | None = None
    # --- memory economy: salience / decay / consolidation / validity ---
    # See docs/theory-of-memory.md sec 5.6 and docs/technical-stack-rfc.md sec 9.
    memory_type: MemoryType = MemoryType.EPISODIC
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    decay_rate: float = Field(default=0.05, ge=0.0)
    reinforcement_count: int = 0
    last_reinforced_ts: str = Field(default_factory=utc_now_iso)
    consolidation_state: ConsolidationState = ConsolidationState.RAW
    # Temporal validity & reconsolidation (docs/theory-of-memory.md sec 5.4-5.5):
    # `subject` is the stable entity/state a memory is about — the key by which a
    # newer reading supersedes an older one. A superseded memory keeps its place
    # in history (valid_until closes its window, superseded_by links its heir) and
    # is dropped from recall as expired, never silently deleted.
    valid_from: str = Field(default_factory=utc_now_iso)
    valid_until: str | None = None
    subject: str | None = None
    superseded_by: str | None = None
    provenance: list[str] = Field(default_factory=list)
    version: int = 1
    # --- converged architecture v1 (docs/theory-of-memory.md sec 8) ---
    # Cross-cutting attributes, not new categories.
    grounding: list[str] = Field(default_factory=list)   # refs to real artifacts (commit, backtest id, log)
    source: MemorySource = MemorySource.OBSERVED         # observed vs inferred vs told
    pinned: bool = False                                  # hard non-decay floor (falsifications must not fade out)
    trigger: str | None = None                           # prospective cue: "time:<iso>" or "condition:<desc>"


class DiscardedDrive(YizhiModel):
    """A competing drive that second-order endorsement did NOT make the will this
    loop, with the reason it was set aside — so the choice between motives is
    auditable, not silent (Frankfurt: the will is the desire the agent endorses,
    not merely the loudest one). See docs/theory-of-will.md."""
    name: str
    intensity: float = Field(ge=0.0, le=1.0)
    reason: str


class Intention(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("intention"))
    ts: str = Field(default_factory=utc_now_iso)
    title: str
    rationale: str
    goal_id: str | None = None
    source_thought_ids: list[str] = Field(default_factory=list)
    drive_names: list[str] = Field(default_factory=list)
    # Second-order endorsement: which competing drive the will endorsed this loop,
    # and the drives it set aside (with reasons). None endorsed => maintenance/hold.
    endorsed_drive: str | None = None
    discarded_drives: list[DiscardedDrive] = Field(default_factory=list)
    active: bool = False
    retired: bool = False


class PlanStepStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"


class PlanStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"   # the cursor ran off the end — every step done/failed


class PlanStep(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("planstep"))
    description: str                                    # one-line intent of this step
    target_command: list[str] = Field(default_factory=list)
    # The EXACT command of the real action this step wants chosen, copied from an
    # ActionProposal in env.propose_actions — NOT free text. [] = no specific target.
    # Same stable action identity the runner and findings.probe_subject use, so a
    # step can only ever name an allowlisted action, never author one.
    target_title: str = ""                             # proposal title, for prompt readability + match
    status: PlanStepStatus = PlanStepStatus.PENDING


class Plan(YizhiModel):
    """A multi-loop plan keyed to the GOAL (not the per-loop intention), held on
    WillState so it persists across loops and resumes from snapshots. The cursor is
    advanced one step per loop (only on a verified-FULL outcome); when it runs off
    the end the plan is COMPLETED. Stall accounting drives deterministic replanning.
    Advisory only: it biases action selection, never the policy/budget gates."""
    id: str = Field(default_factory=lambda: new_id("plan"))
    ts: str = Field(default_factory=utc_now_iso)
    goal_id: str
    steps: list[PlanStep]
    cursor: int = 0                                    # index of the active step; == len(steps) when complete
    stall_count: int = 0                               # deterministic no-progress counter
    revision: int = 0                                  # bumped on each replan
    status: PlanStatus = PlanStatus.ACTIVE
    expected_verification: list[str] = Field(default_factory=list)


class ActionProposal(YizhiModel):
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


class PolicyGateResult(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("policy"))
    ts: str = Field(default_factory=utc_now_iso)
    proposal_id: str
    allowed: bool
    decision: str
    reasons: list[str] = Field(default_factory=list)


class ActionRecord(YizhiModel):
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


class VerificationResult(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("verify"))
    ts: str = Field(default_factory=utc_now_iso)
    action_record_id: str | None = None
    passed: bool
    checks: list[str] = Field(default_factory=list)
    summary: str


class Reflection(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("reflection"))
    ts: str = Field(default_factory=utc_now_iso)
    loop_id: str
    content: str
    learned: list[str] = Field(default_factory=list)
    next_memory: MemoryRecord | None = None


class SkillRecord(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("skill"))
    ts: str = Field(default_factory=utc_now_iso)
    name: str
    description: str
    source_reflection_ids: list[str] = Field(default_factory=list)


class EvalEvent(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("eval"))
    ts: str = Field(default_factory=utc_now_iso)
    loop_id: str
    status: LoopStatus
    metrics: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class AutonomousValueLoop(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("loop"))
    ts: str = Field(default_factory=utc_now_iso)
    status: LoopStatus
    environment: EnvironmentName
    observation_ids: list[str] = Field(default_factory=list)
    thought_ids: list[str] = Field(default_factory=list)
    drive_ids: list[str] = Field(default_factory=list)
    intention_id: str | None = None
    plan_id: str | None = None
    proposal_id: str | None = None
    policy_result_id: str | None = None
    action_record_id: str | None = None
    verification_result_id: str | None = None
    reflection_id: str | None = None
    eval_event_id: str | None = None


# --- delegation to an external coding harness (R0; docs/resident-operator-plan.md) ---
# Will delegates bounded, read-only repo work to a coding-harness CLI (Claude Code /
# Codex). The harness is the HAND, never the will: every task is a NETWORK_READ-class
# ActionProposal that must pass the policy gate, spend existence budget, and land as
# DELEGATION_* semantic events. Write/apply is a separate governed stage, not here.


class DelegationKind(StrEnum):
    ANALYZE_REPO = "analyze_repo"
    SUMMARIZE_TESTS = "summarize_tests"
    INSPECT_DOCS = "inspect_docs"
    PROPOSE_PATCH = "propose_patch"   # R1; defined now but denied by the R0 read-only gate


class DelegationTask(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("delegation"))
    ts: str = Field(default_factory=utc_now_iso)
    kind: DelegationKind
    instruction: str                                        # free-text brief; safety lives in the gate, not here
    cwd: str                                                # restricted in-repo relative path the harness may read
    allowed_tools: list[str] = Field(default_factory=list)  # read-only tool names handed to the harness
    allow_write: bool = False                               # R0 must be False; the gate denies True
    cost: float = 2.0                                       # existence-budget cost (network_read class)


class DelegationReport(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("delegation-report"))
    ts: str = Field(default_factory=utc_now_iso)
    task_id: str
    ok: bool
    summary: str
    artifacts: list[str] = Field(default_factory=list)  # paths produced (empty for pure read-only analysis)
    raw_output_ref: str = ""                            # archive ref to the full harness transcript
    cost_spent: float = 0.0
    error: str | None = None
