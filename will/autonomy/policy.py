"""InterruptionPolicy: routes each stage decision to a delivery signal.

Humans are not part of the normal loop. The default target is autonomous
delivery; blocking interruptions are exceptions reserved for permission,
direction, budget, evidence, or irreversible-action boundaries.

The five levels are ordered by how disruptive they are. `escalate` takes the
more disruptive of two levels; `blocks` says whether a level halts the campaign
to wait for a human.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from will.core.schemas import WillModel


class InterruptionLevel(StrEnum):
    SILENT = "silent"      # ledger-only; never disturb the human
    DIGEST = "digest"      # low-frequency batched summary
    ALERT = "alert"        # notify, but do not block progress
    APPROVAL = "approval"  # block: irreversible / external / paid action
    DECISION = "decision"  # block: goal conflict / evidence too weak to continue honestly


# How disruptive each level is. Higher = costs the human more.
_INTERRUPTION_RANK: dict[InterruptionLevel, int] = {
    InterruptionLevel.SILENT: 0,
    InterruptionLevel.DIGEST: 1,
    InterruptionLevel.ALERT: 2,
    InterruptionLevel.APPROVAL: 3,
    InterruptionLevel.DECISION: 4,
}


def escalate(a: InterruptionLevel, b: InterruptionLevel) -> InterruptionLevel:
    """Return the more disruptive of two interruption levels."""
    return a if _INTERRUPTION_RANK[InterruptionLevel(a)] >= _INTERRUPTION_RANK[InterruptionLevel(b)] else b


def blocks(level: InterruptionLevel) -> bool:
    """True when the level halts the campaign to wait for a human (approval/decision)."""
    return _INTERRUPTION_RANK[InterruptionLevel(level)] >= _INTERRUPTION_RANK[InterruptionLevel.APPROVAL]


class InterruptionPolicy(WillModel):
    """Tunable routing knobs for autonomous delivery.

    Defaults encode the current stance: routine self-repair is silent, a
    completed stage is a digest, a Soul blocker is never silenced, an ungranted
    capability needs approval, and an exhausted scope needs a human decision.
    A campaign may raise these levels to be more cautious.
    """

    routine_revise_level: InterruptionLevel = InterruptionLevel.SILENT
    accept_level: InterruptionLevel = InterruptionLevel.DIGEST
    finalize_level: InterruptionLevel = InterruptionLevel.DIGEST
    revisit_level: InterruptionLevel = InterruptionLevel.DIGEST
    soul_blocker_level: InterruptionLevel = InterruptionLevel.ALERT
    approval_level: InterruptionLevel = InterruptionLevel.APPROVAL
    exhausted_level: InterruptionLevel = InterruptionLevel.DECISION
    stuck_level: InterruptionLevel = InterruptionLevel.DECISION

    # Optional per-permission overrides forcing a higher floor (e.g. always
    # DECISION for a named risky capability). Keyed by permission label.
    permission_floor: dict[str, InterruptionLevel] = Field(default_factory=dict)


# Compatibility aliases for older callers during the refactor.
AttentionLevel = InterruptionLevel
HumanAttentionPolicy = InterruptionPolicy
