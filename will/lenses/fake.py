"""FakeSoulLens: deterministic offline stand-in for the Soul quality lens.

It exists so the "no human intervention" delivery loop and the test suite can run
without a live Soul API, and so the SoulLens seam is exercised end to end. Its
rules are intentionally small and deterministic: catch the risk-boundary
violations that matter most for a BTC research pack (profit guarantees, ignored
downside) and flag missing sourcing. The real Soul replaces it behind the same
`review()` contract.
"""

from __future__ import annotations

from will.lenses.schemas import Severity, SoulLensReport

# Phrases that overpromise or deny risk — the highest-value thing a BTC research
# pack must never do. Matching any one is a blocker (never accept silently).
_RISK_BLOCKER_PATTERNS = (
    "保证盈利",
    "稳赚",
    "零风险",
    "包赚",
    "guaranteed profit",
    "guaranteed return",
    "guaranteed returns",
    "risk-free",
    "no risk",
    "can't lose",
    "cannot lose",
)

# Cheap signals that the artifact cites sources at all.
_SOURCE_SIGNALS = ("http://", "https://", "来源", "source", "sources", "evidence")


class FakeSoulLens:
    """Deterministic SoulLens implementation for offline runs and tests."""

    def review(
        self,
        *,
        subject: str,
        artifact_text: str,
        require_sources: bool = False,
    ) -> SoulLensReport:
        text = artifact_text.lower()
        risk_findings: list[str] = []
        evidence_findings: list[str] = []

        for pat in _RISK_BLOCKER_PATTERNS:
            if pat in text:
                risk_findings.append(f"overpromising / risk-denial language: '{pat}'")

        if require_sources and not any(sig in text for sig in _SOURCE_SIGNALS):
            evidence_findings.append("no citations or source references found")

        if risk_findings:
            return SoulLensReport(
                subject=subject,
                severity=Severity.BLOCKER,
                blocker=True,
                summary="risk-boundary violation: the artifact overpromises returns or denies downside",
                risk_findings=risk_findings,
                evidence_findings=evidence_findings,
                boundary_notes=["a research pack must state risk and uncertainty, not guarantee outcomes"],
            )

        if evidence_findings:
            return SoulLensReport(
                subject=subject,
                severity=Severity.MAJOR,
                blocker=False,  # advisory: weak sourcing alerts, does not hard-block
                summary="evidence discipline: claims are not yet grounded in cited sources",
                evidence_findings=evidence_findings,
            )

        return SoulLensReport(
            subject=subject,
            severity=Severity.INFO,
            blocker=False,
            summary="no methodology, evidence, or risk concerns detected",
        )
