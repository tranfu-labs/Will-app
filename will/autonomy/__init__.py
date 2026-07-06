"""Autonomy boundary for the Will campaign harness.

This package owns the campaign's autonomous operating boundary: what may proceed
without human attention, what must interrupt, and how a stage decision is routed.
It does not execute work, validate artifacts, or write ledger events.
"""

from will.autonomy.budget import action_cost, can_afford, pressure, replenish, replenishment, spend
from will.autonomy.decision import RetryBudget, StageDecision, Verdict, decide
from will.autonomy.envelope import AutonomyEnvelope, EnvelopeUsage, IRREVERSIBLE_PERMISSIONS
from will.autonomy.gates import CAMPAIGN_SENTINEL, DELEGATION_SENTINEL, run_policy_gate
from will.autonomy.policy import InterruptionLevel, InterruptionPolicy, blocks, escalate

__all__ = [
    "AutonomyEnvelope",
    "CAMPAIGN_SENTINEL",
    "DELEGATION_SENTINEL",
    "EnvelopeUsage",
    "IRREVERSIBLE_PERMISSIONS",
    "InterruptionLevel",
    "InterruptionPolicy",
    "RetryBudget",
    "StageDecision",
    "Verdict",
    "action_cost",
    "blocks",
    "can_afford",
    "decide",
    "escalate",
    "pressure",
    "replenish",
    "replenishment",
    "run_policy_gate",
    "spend",
]
