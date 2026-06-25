"""The existence budget economy (docs/theory-of-will.md Axiom Nine).

Stake made operational: thinking and acting burn a finite viability resource, and
only externally verified value replenishes it. The numbers are tuned so a verified
(FULL) loop is roughly net-positive while a failed or blocked loop is net-negative —
so a productive agent slowly accumulates headroom and an unproductive one drifts
toward the halt threshold and stops. Deterministic v0: pure functions over the
ExistenceBudget, returning updated copies; the loop persists and audits them.
"""

from __future__ import annotations

from yizhi.core.schemas import ActionClass, ExistenceBudget, LoopStatus

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
    ActionClass.MEMORY.value: 0.5,
    ActionClass.INTERNAL.value: 0.5,
}

# Replenishment is realized value. Completing a verified loop is worth a little,
# but the loop's real value is producing NEW evidence (the knowledge bonus). So a
# loop that produces nothing new is net-negative — even a cheap one — and the agent
# cannot sustain itself on routine checks: it must keep discovering.
_REPLENISH: dict[str, float] = {
    LoopStatus.FULL.value: 1.0,
    LoopStatus.PARTIAL.value: 0.5,
    LoopStatus.FAILED.value: 0.0,
    LoopStatus.BLOCKED.value: 0.0,
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


def replenishment(status: LoopStatus | str) -> float:
    value = status.value if isinstance(status, LoopStatus) else str(status)
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
