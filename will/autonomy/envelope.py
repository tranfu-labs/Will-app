"""AutonomyEnvelope — the circuit breaker that makes unattended delivery safe.

The human authorises a *boundary*, not each step. Inside the envelope Will
advances silently; crossing it (an irreversible/forbidden action, or an exhausted
limit) forces a human back into the loop. This bounds the blast radius of
long-horizon fragility (RESEARCH.md §3) instead of trusting a worker to run free.

An envelope is a permission grant + a set of hard ceilings. `EnvelopeUsage`
carries the running counters compared against those ceilings each tick.
"""

from __future__ import annotations

from pydantic import Field

from will.core.ids import new_id
from will.core.schemas import WillModel
from will.core.time import utc_now_iso

# Irreversible / external capability labels that must never be crossed silently.
# A low-attention campaign may only touch these after explicit human approval, so
# they default into every envelope's `forbidden` set regardless of what is granted.
IRREVERSIBLE_PERMISSIONS = frozenset(
    {
        "trading",
        "credential_access",
        "paid_data",
        "remote_write",
        "commit_push_deploy",
    }
)


class AutonomyEnvelope(WillModel):
    """A human-authorised autonomy boundary for one campaign.

    Inside the boundary Will advances without asking. The boundary is defined by
    what capabilities are granted (`allowed_permissions`, minus `forbidden`) and
    by hard ceilings on how much unattended work may happen (ticks, worker runs,
    revisions, revisits, cost).
    """

    id: str = Field(default_factory=lambda: new_id("envelope"))
    ts: str = Field(default_factory=utc_now_iso)
    campaign_id: str
    objective: str
    # Advance freely until this stage id is reached; None => the whole campaign.
    until_stage: str | None = None
    # Hard ceilings — reaching any one trips the breaker (verdict=pause).
    max_ticks: int = 24
    max_worker_runs: int = 8
    max_revisions: int = 2
    max_revisits: int = 2
    max_cost: float = 5.0
    # Capabilities granted inside the boundary. A capability not listed here, or
    # listed in `forbidden`, escalates to approval instead of running silently.
    allowed_permissions: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=lambda: sorted(IRREVERSIBLE_PERMISSIONS))
    # How often to batch a silent-progress summary to the human (minutes).
    digest_interval_minutes: int = 30

    def permits(self, permission: str) -> bool:
        """A capability is permitted only if explicitly granted and never forbidden."""
        if permission in self.forbidden:
            return False
        return permission in self.allowed_permissions

    def requires_approval(self, permission: str) -> bool:
        """An action needs a human when its capability is forbidden or ungranted."""
        return not self.permits(permission)


class EnvelopeUsage(WillModel):
    """Running counters compared against an envelope's ceilings each tick."""

    ticks_used: int = 0
    worker_runs_used: int = 0
    revisions_used: int = 0
    revisits_used: int = 0
    cost_used: float = 0.0

    def tripped_limits(self, envelope: AutonomyEnvelope) -> list[str]:
        """Return the names of global ceilings that have been reached.

        Empty list => still inside the boundary. A non-empty list means the
        circuit breaker has tripped and the tick must pause for a human.

        Only the *global* resource ceilings (ticks, worker runs, cost) live here —
        they mean "the whole campaign is out of allowance, a human must extend or
        accept". The per-stage revise/revisit budgets are NOT breaker conditions:
        `decide()` degrades them gracefully (revise -> revisit -> human decision).
        """
        tripped: list[str] = []
        if self.ticks_used >= envelope.max_ticks:
            tripped.append("max_ticks")
        if self.worker_runs_used >= envelope.max_worker_runs:
            tripped.append("max_worker_runs")
        if self.cost_used >= envelope.max_cost:
            tripped.append("max_cost")
        return tripped
