"""SoulLens: the read-only quality lens contract.

Soul is the methodology / evidence-discipline / risk lens. It compresses the
judgement a human would otherwise have to supply ("is this result any good?") into
a structured, evidence-bearing report. The boundary is fixed:

    Will owns agency; Soul owns critique; humans own authority.

A lens is advisory and read-only: it returns a `SoulLensReport`, never writes
WillState, never advances a campaign, never spends budget. Will records adoption
and a Soul blocker is never silently ignored by the autonomy decision.
Soul itself is not fully reliable, so its verdict informs but does not bind.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import Field

from will.core.ids import new_id
from will.core.schemas import WillModel
from will.core.time import utc_now_iso


class Severity(StrEnum):
    INFO = "info"        # observation only
    MINOR = "minor"      # worth noting, not worth reworking
    MAJOR = "major"      # should be addressed before delivery
    BLOCKER = "blocker"  # continuing as-is would mislead — do not accept silently


class SoulLensReport(WillModel):
    """A read-only quality report over one artifact.

    `blocker` is the single bit `autonomy.decide()` consumes; `summary` becomes
    the human-facing reason. Findings are grouped by the three things Soul checks:
    methodology (is the approach sound?), evidence (are claims sourced?), and risk
    (does it overpromise / ignore downside?).
    """

    id: str = Field(default_factory=lambda: new_id("soul-report"))
    ts: str = Field(default_factory=utc_now_iso)
    subject: str
    severity: Severity = Severity.INFO
    blocker: bool = False
    summary: str = ""
    methodology_findings: list[str] = Field(default_factory=list)
    evidence_findings: list[str] = Field(default_factory=list)
    risk_findings: list[str] = Field(default_factory=list)
    boundary_notes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


@runtime_checkable
class SoulLens(Protocol):
    """The seam Will calls. A real Soul API and the FakeSoulLens both satisfy it."""

    def review(
        self,
        *,
        subject: str,
        artifact_text: str,
        require_sources: bool = False,
    ) -> SoulLensReport: ...
