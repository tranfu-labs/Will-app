"""Autonomy layer: envelope circuit breaker + interruption routing.

These tests pin the deterministic decision brain — the concrete answer to
"advance autonomously, or request an exception?". No I/O, no LLM.
"""

from __future__ import annotations

from will.autonomy import (
    InterruptionLevel,
    AutonomyEnvelope,
    EnvelopeUsage,
    InterruptionPolicy,
    Verdict,
    StageDecision,
    blocks,
    decide,
    escalate,
)


def _envelope(**kw) -> AutonomyEnvelope:
    base = dict(
        campaign_id="btc-mvp",
        objective="answer BTC question",
        allowed_permissions=["web_read", "write_local_artifact", "run_local_backtest"],
        max_revisions=2,
        max_revisits=2,
    )
    base.update(kw)
    return AutonomyEnvelope(**base)


# --- envelope permission boundary ---


def test_granted_capability_is_permitted():
    env = _envelope()
    assert env.permits("web_read")
    assert not env.requires_approval("web_read")


def test_forbidden_capability_is_never_permitted_even_if_granted():
    env = _envelope(allowed_permissions=["trading", "web_read"])
    # trading is in the default forbidden set, so granting it does not permit it
    assert not env.permits("trading")
    assert env.requires_approval("trading")


def test_ungranted_capability_requires_approval():
    env = _envelope()
    assert env.requires_approval("paid_data")


# --- interruption level helpers ---


def test_escalate_returns_more_disruptive_level():
    assert escalate(InterruptionLevel.SILENT, InterruptionLevel.APPROVAL) == InterruptionLevel.APPROVAL
    assert escalate(InterruptionLevel.DECISION, InterruptionLevel.DIGEST) == InterruptionLevel.DECISION


def test_blocks_only_for_approval_and_decision():
    assert not blocks(InterruptionLevel.SILENT)
    assert not blocks(InterruptionLevel.DIGEST)
    assert not blocks(InterruptionLevel.ALERT)
    assert blocks(InterruptionLevel.APPROVAL)
    assert blocks(InterruptionLevel.DECISION)


# --- decide(): the routing brain ---


def test_passing_middle_stage_accepts_silently_as_digest():
    d = decide(
        envelope=_envelope(),
        usage=EnvelopeUsage(),
        stage_id="S2",
        is_final_stage=False,
        validation_passed=True,
    )
    assert d.verdict == Verdict.ACCEPT
    assert d.interruption == InterruptionLevel.DIGEST
    assert not blocks(d.interruption)


def test_passing_final_stage_finalizes():
    d = decide(
        envelope=_envelope(),
        usage=EnvelopeUsage(),
        stage_id="S5",
        is_final_stage=True,
        validation_passed=True,
    )
    assert d.verdict == Verdict.FINALIZE


def test_routine_validation_failure_revises_silently_without_human():
    d = decide(
        envelope=_envelope(),
        usage=EnvelopeUsage(revisions_used=0),
        stage_id="S3",
        is_final_stage=False,
        validation_passed=False,
        validation_reasons=["missing sources section"],
    )
    assert d.verdict == Verdict.REVISE
    assert d.interruption == InterruptionLevel.SILENT
    assert "missing sources" in d.reason


def test_revision_budget_spent_revisits_then_asks_human():
    env = _envelope(max_revisions=1, max_revisits=1)
    # revisions spent, revisits available -> revisit (digest, no block)
    d1 = decide(
        envelope=env,
        usage=EnvelopeUsage(revisions_used=1, revisits_used=0),
        stage_id="S3",
        is_final_stage=False,
        validation_passed=False,
    )
    assert d1.verdict == Verdict.REVISIT
    assert not blocks(d1.interruption)
    # both spent -> escalate to a human decision
    d2 = decide(
        envelope=env,
        usage=EnvelopeUsage(revisions_used=1, revisits_used=1),
        stage_id="S3",
        is_final_stage=False,
        validation_passed=False,
    )
    assert d2.verdict == Verdict.ASK_HUMAN
    assert d2.interruption == InterruptionLevel.DECISION


def test_ungranted_permission_forces_approval_before_any_progress():
    d = decide(
        envelope=_envelope(),
        usage=EnvelopeUsage(),
        stage_id="S3",
        is_final_stage=False,
        validation_passed=True,
        required_permission="paid_data",
    )
    assert d.verdict == Verdict.ASK_HUMAN
    assert d.interruption == InterruptionLevel.APPROVAL
    assert blocks(d.interruption)


def test_soul_blocker_is_never_silenced():
    d = decide(
        envelope=_envelope(),
        usage=EnvelopeUsage(),
        stage_id="S2",
        is_final_stage=False,
        validation_passed=True,  # gate passed, but Soul objects
        soul_blocker=True,
        soul_reason="weak source coverage",
    )
    assert d.verdict == Verdict.REVISE
    assert d.interruption == InterruptionLevel.ALERT  # at least an alert, not silent
    assert "weak source coverage" in d.reason


def test_soul_blocker_past_budget_escalates_to_decision():
    env = _envelope(max_revisions=1)
    d = decide(
        envelope=env,
        usage=EnvelopeUsage(revisions_used=1),
        stage_id="S2",
        is_final_stage=False,
        validation_passed=True,
        soul_blocker=True,
        soul_reason="unsupported profit claim",
    )
    assert d.verdict == Verdict.ASK_HUMAN
    assert d.interruption == InterruptionLevel.DECISION


def test_exhausted_envelope_pauses_before_everything():
    env = _envelope(max_ticks=3)
    d = decide(
        envelope=env,
        usage=EnvelopeUsage(ticks_used=3),
        stage_id="S3",
        is_final_stage=False,
        validation_passed=False,  # would normally revise, but the breaker trips first
        required_permission="paid_data",  # would normally need approval; pause wins
    )
    assert d.verdict == Verdict.PAUSE
    assert d.interruption == InterruptionLevel.DECISION
    assert "max_ticks" in d.reason


def test_retry_budget_is_surfaced_on_the_decision():
    d = decide(
        envelope=_envelope(max_revisions=2, max_revisits=2),
        usage=EnvelopeUsage(revisions_used=1, revisits_used=0),
        stage_id="S3",
        is_final_stage=False,
        validation_passed=True,
    )
    assert d.retry_budget.remaining_revisions == 1
    assert d.retry_budget.remaining_revisits == 2


def test_permission_floor_raises_interruption_for_named_capability():
    policy = InterruptionPolicy(permission_floor={"web_read": InterruptionLevel.ALERT})
    d = decide(
        envelope=_envelope(),
        usage=EnvelopeUsage(),
        stage_id="S2",
        is_final_stage=False,
        validation_passed=True,
        required_permission="web_read",  # granted, so no approval, but floored to ALERT
        policy=policy,
    )
    assert d.verdict == Verdict.ACCEPT
    assert d.interruption == InterruptionLevel.ALERT


def test_decision_is_a_projection_not_mutated_state():
    d = decide(
        envelope=_envelope(),
        usage=EnvelopeUsage(),
        stage_id="S1",
        is_final_stage=False,
        validation_passed=True,
        evidence_refs=["deliverable-abc"],
    )
    assert isinstance(d, StageDecision)
    assert d.evidence_refs == ["deliverable-abc"]
    assert d.campaign_id == "btc-mvp"
