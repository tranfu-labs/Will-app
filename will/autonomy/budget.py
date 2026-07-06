"""The Will budget economy.

Campaign ticks and worker actions burn a finite allowance. Verified delivery can
replenish it, while failed or blocked work drains it toward a halt threshold. The
budget is governance pressure, not an old cognition-loop currency.
"""

from __future__ import annotations

from enum import StrEnum

from will.core.schemas import ActionClass, ExistenceBudget


class WorkStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"

# Thinking is not free: every loop burns a base cognitive cost even if it acts on
# nothing. This is what makes a continuous default-mode loop economically bounded.
COGNITION_COST = 1.0

# Acting costs more the more it can affect — high-stake classes burn more. (Most
# are gated by policy in v0; the cost still expresses how much is at risk.)
_ACTION_COST: dict[str, float] = {
    ActionClass.FINANCIAL.value: 5.0,
    ActionClass.EXTERNAL_WRITE.value: 5.0,
    ActionClass.CREDENTIAL.value: 5.0,
    ActionClass.SELF_MODIFY.value: 5.0,
    ActionClass.REPRODUCE.value: 5.0,
    ActionClass.NETWORK_READ.value: 2.0,
    ActionClass.ARTIFACT.value: 2.0,
    ActionClass.INTERNAL.value: 0.5,
}

# Replenishment is realized value. Completing a verified loop is worth a little,
# but the loop's real value is producing NEW evidence (the knowledge bonus). So a
# loop that produces nothing new is net-negative — even a cheap one — and the agent
# cannot sustain itself on routine checks: it must keep discovering.
_REPLENISH: dict[str, float] = {
    WorkStatus.COMPLETED.value: 1.0,
    WorkStatus.PARTIAL.value: 0.5,
    WorkStatus.FAILED.value: 0.0,
    WorkStatus.BLOCKED.value: 0.0,
}

# Discovering genuinely NEW edge-knowledge from a real experiment probe is the main
# replenishment — enough that a financial probe (cost 6: cognition 1 + action 5) is
# net-positive when it finds something new, and net-negative when it re-confirms the
# known. This closes the stake loop: the agent earns by learning, and coasting on
# routine checks (no new evidence) slowly drains it toward the halt threshold.
KNOWLEDGE_REPLENISH = 7.0


def action_cost(action_class: ActionClass | str) -> float:
    value = action_class.value if isinstance(action_class, ActionClass) else str(action_class)
    return _ACTION_COST.get(value, 1.0)


def replenishment(status: WorkStatus | str) -> float:
    value = status.value if isinstance(status, WorkStatus) else str(status)
    return _REPLENISH.get(value, 0.0)


def can_afford(budget: ExistenceBudget, amount: float) -> bool:
    """True if spending `amount` keeps the balance at or above the halt threshold.
    A budget already halted can afford nothing — the agent has stopped acting."""
    if budget.halted:
        return False
    return budget.balance - amount >= budget.halt_threshold


def pressure(budget: ExistenceBudget) -> float:
    """How close to halting, in [0, 1]: 0 at full headroom, 1 at the threshold.
    Budget pressure is what grounds salience — memory near halt matters more."""
    span = budget.initial - budget.halt_threshold
    if span <= 0:
        return 1.0
    headroom = (budget.balance - budget.halt_threshold) / span
    return _clamp(1.0 - headroom)


def spend(budget: ExistenceBudget, amount: float) -> ExistenceBudget:
    """Burn `amount`; mark halted if the balance reaches the threshold."""
    balance = budget.balance - amount
    return budget.model_copy(
        update={
            "balance": balance,
            "total_spent": budget.total_spent + amount,
            "spend_count": budget.spend_count + 1,
            "halted": balance <= budget.halt_threshold,
        }
    )


def replenish(budget: ExistenceBudget, amount: float) -> ExistenceBudget:
    """Add externally verified value; clears the halt if it lifts above threshold."""
    if amount <= 0:
        return budget
    balance = budget.balance + amount
    return budget.model_copy(
        update={
            "balance": balance,
            "total_replenished": budget.total_replenished + amount,
            "replenish_count": budget.replenish_count + 1,
            "halted": balance <= budget.halt_threshold,
        }
    )


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value
