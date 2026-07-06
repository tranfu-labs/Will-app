"""StageDecision and the deterministic `decide()` that produces it.

Append-only events remain the source of truth; a StageDecision is the recorded
projection of one campaign tick. It is where the worker's candidate result, the
acceptance-gate validation, an optional Soul lens report, the policy/permission
check, and the autonomy scope collapse into one verdict and one interruption
level.

`decide()` is pure and deterministic: workers produce candidates, Soul critiques
them, and Will decides whether to accept, revise, revisit, finalize, pause, or
request a human exception.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from will.autonomy.envelope import AutonomyEnvelope, EnvelopeUsage
from will.autonomy.policy import InterruptionLevel, InterruptionPolicy, escalate
from will.core.ids import new_id
from will.core.schemas import WillModel
from will.core.time import utc_now_iso


class Verdict(StrEnum):
    CONTINUE = "continue"    # keep working the stage; no deliverable to judge yet
    ACCEPT = "accept"        # deliverable passed the gate; accept and advance
    REVISE = "revise"        # rework within the current stage (routine self-repair)
    REVISIT = "revisit"      # revision budget spent; rework an earlier stage
    ASK_HUMAN = "ask_human"  # needs a human (approval or decision)
    PAUSE = "pause"          # envelope exhausted; hold until a human extends/accepts
    BLOCK = "block"          # hard policy deny (safety class); do not run
    FINALIZE = "finalize"    # last stage passed; synthesise the final delivery


class RetryBudget(WillModel):
    """What the envelope still allows, surfaced on the decision for auditability."""

    remaining_revisions: int = 0
    remaining_revisits: int = 0


class StageDecision(WillModel):
    """The per-tick campaign route decision.

    Aggregates worker_result + validation + soul_report + policy + envelope into
    one verdict and one interruption level. Not a source of truth — the ledger
    is — but the object the controller and shell projections read.
    """

    id: str = Field(default_factory=lambda: new_id("decision"))
    ts: str = Field(default_factory=utc_now_iso)
    campaign_id: str
    stage_id: str
    verdict: Verdict
    interruption: InterruptionLevel
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    next_instruction: str = ""
    retry_budget: RetryBudget = Field(default_factory=RetryBudget)

    @property
    def attention(self) -> InterruptionLevel:
        """Compatibility alias for older callers."""
        return self.interruption


def _retry_budget(envelope: AutonomyEnvelope, usage: EnvelopeUsage) -> RetryBudget:
    return RetryBudget(
        remaining_revisions=max(0, envelope.max_revisions - usage.revisions_used),
        remaining_revisits=max(0, envelope.max_revisits - usage.revisits_used),
    )


def decide(
    *,
    envelope: AutonomyEnvelope,
    usage: EnvelopeUsage,
    stage_id: str,
    is_final_stage: bool,
    validation_passed: bool,
    validation_reasons: list[str] | None = None,
    required_permission: str | None = None,
    soul_blocker: bool = False,
    soul_reason: str = "",
    evidence_refs: list[str] | None = None,
    policy: InterruptionPolicy | None = None,
) -> StageDecision:
    """Collapse one tick's facts into a StageDecision.

    Rules are evaluated safety/escalation-first (first match wins):

    1. envelope exhausted            -> PAUSE / decision
    2. capability needs approval     -> ASK_HUMAN / approval
    3. Soul blocker (never silenced) -> REVISE within budget (alert), else ASK_HUMAN / decision
    4. acceptance gate failed        -> REVISE (silent) -> REVISIT (digest) -> ASK_HUMAN / decision
    5. acceptance gate passed        -> FINALIZE (last stage) or ACCEPT, both digest
    """
    policy = policy or InterruptionPolicy()
    reasons = validation_reasons or []
    refs = evidence_refs or []
    retry = _retry_budget(envelope, usage)

    def build(verdict: Verdict, interruption: InterruptionLevel, reason: str, nxt: str = "") -> StageDecision:
        floor = policy.permission_floor.get(required_permission or "")
        if floor is not None:
            interruption = escalate(interruption, floor)
        return StageDecision(
            campaign_id=envelope.campaign_id,
            stage_id=stage_id,
            verdict=verdict,
            interruption=interruption,
            reason=reason,
            evidence_refs=refs,
            next_instruction=nxt,
            retry_budget=retry,
        )

    # 1. The circuit breaker trips before anything else — a depleted campaign halts.
    tripped = usage.tripped_limits(envelope)
    if tripped:
        return build(
            Verdict.PAUSE,
            policy.exhausted_level,
            f"autonomy envelope exhausted: {', '.join(tripped)}",
            "await human extension or acceptance of current limitations",
        )

    # 2. Crossing the permission boundary is the only mandatory interruption inside
    #    a live envelope — a pre-declared boundary, not runtime babysitting.
    if required_permission and envelope.requires_approval(required_permission):
        return build(
            Verdict.ASK_HUMAN,
            policy.approval_level,
            f"capability '{required_permission}' is outside the autonomy envelope",
            f"await human approval for '{required_permission}'",
        )

    # 3. A Soul blocker is advisory but is never silently ignored.
    if soul_blocker:
        if usage.revisions_used < envelope.max_revisions:
            return build(
                Verdict.REVISE,
                policy.soul_blocker_level,
                f"soul lens blocker: {soul_reason or 'methodology/evidence/risk concern'}",
                "address the soul blocker and resubmit",
            )
        return build(
            Verdict.ASK_HUMAN,
            policy.stuck_level,
            f"soul blocker unresolved within revise budget: {soul_reason}",
            "human decision needed on whether to continue despite the concern",
        )

    # 4. A failed acceptance gate is handled by the system first: routine self-repair
    #    (silent), then an earlier-stage revisit (digest), then — only if the budget
    #    is spent — a human.
    if not validation_passed:
        detail = "; ".join(reasons) or "acceptance gate failed"
        if usage.revisions_used < envelope.max_revisions:
            return build(Verdict.REVISE, policy.routine_revise_level, detail, "revise the artifact")
        if usage.revisits_used < envelope.max_revisits:
            return build(Verdict.REVISIT, policy.revisit_level, detail, "revisit an earlier stage")
        return build(
            Verdict.ASK_HUMAN,
            policy.stuck_level,
            f"cannot satisfy acceptance gate within budget: {detail}",
            "human decision needed on scope or acceptance criteria",
        )

    # 5. Passed. Advance (or finalize) — a completed stage is digest-worthy, not silent,
    #    so the human stays oriented without being interrupted.
    if is_final_stage:
        return build(Verdict.FINALIZE, policy.finalize_level, "final stage accepted", "synthesise the final delivery pack")
    return build(Verdict.ACCEPT, policy.accept_level, "deliverable accepted", "advance to the next stage")


# Compatibility alias for older callers during the refactor.
WillDecision = StageDecision
