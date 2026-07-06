"""SoulLens contract + FakeSoulLens (ADR-005, ADR-007).

Also pins the integration point that matters: a Soul blocker flowing into
autonomy.decide() is never silently ignored.
"""

from __future__ import annotations

from will.autonomy import InterruptionLevel, AutonomyEnvelope, EnvelopeUsage, Verdict, decide
from will.lenses import FakeSoulLens, Severity, SoulLens, SoulLensReport


def test_fake_lens_satisfies_protocol():
    assert isinstance(FakeSoulLens(), SoulLens)


def test_clean_artifact_is_info_not_blocker():
    report = FakeSoulLens().review(
        subject="S2 BTC basics",
        artifact_text="BTC is a decentralized asset. Trading has fees and volatility risk. source: https://x",
        require_sources=True,
    )
    assert report.severity == Severity.INFO
    assert report.blocker is False


def test_profit_guarantee_is_a_blocker():
    report = FakeSoulLens().review(
        subject="S5 research pack",
        artifact_text="Buy BTC now for guaranteed profit, it is risk-free.",
    )
    assert report.blocker is True
    assert report.severity == Severity.BLOCKER
    assert report.risk_findings


def test_missing_sources_is_major_but_advisory():
    report = FakeSoulLens().review(
        subject="S2 BTC basics",
        artifact_text="BTC is a currency and here are some opinions with no citations.",
        require_sources=True,
    )
    assert report.severity == Severity.MAJOR
    assert report.blocker is False
    assert report.evidence_findings


def test_report_is_read_only_projection():
    report = SoulLensReport(subject="x", summary="hi")
    assert report.subject == "x"
    # advisory report carries no authority to mutate anything — it is plain data
    assert report.evidence_refs == []


def test_soul_blocker_flows_into_decision_as_non_silent():
    """The load-bearing integration: a Soul blocker reaches decide() and forces at
    least an alert-level rework rather than a silent accept."""
    env = AutonomyEnvelope(
        campaign_id="btc-mvp",
        objective="answer BTC question",
        allowed_permissions=["web_read", "write_local_artifact"],
        max_revisions=2,
    )
    report = FakeSoulLens().review(
        subject="S5",
        artifact_text="guaranteed profit with no risk",
    )
    decision = decide(
        envelope=env,
        usage=EnvelopeUsage(),
        stage_id="S5",
        is_final_stage=True,
        validation_passed=True,  # the deterministic gate passed; only Soul objects
        soul_blocker=report.blocker,
        soul_reason=report.summary,
    )
    assert decision.verdict == Verdict.REVISE
    assert decision.interruption == InterruptionLevel.ALERT
    assert "risk-boundary" in decision.reason
