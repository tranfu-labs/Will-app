"""Plan creation and proposal selection.

Proposal selection is deterministic by default. When an LLM is enabled (opt-in),
the LLM *selects among the environment's allow-listed proposals* by index — it
chooses which safe action best advances the will's goal/intention, but it can
NEVER author a command: it picks from the menu the environment declared. This is
the second wall; the first is `run_policy_gate`, which still checks the chosen
proposal against an exact command allowlist. So the LLM's richer cognition can
drive *which* action, while execution stays inside the environment's paper-safe
envelope. Any LLM failure degrades to the deterministic chooser and is signalled.
"""

from __future__ import annotations

from yizhi.core.schemas import ActionProposal, ActionClass, EnvironmentName, Intention, PlanStep
from yizhi.engine.recall_render import render_recall


def _noop(env_name: EnvironmentName | str) -> ActionProposal:
    return ActionProposal(
        environment=EnvironmentName(env_name),
        action_class=ActionClass.INTERNAL,
        title="No-op observation proposal",
        command=[],
        description="No proposal was available.",
        dry_run=True,
    )


def _deterministic_choose(proposals: list[ActionProposal]) -> ActionProposal:
    safe_internal = [p for p in proposals if p.action_class == ActionClass.INTERNAL and p.dry_run]
    if safe_internal:
        return safe_internal[0]
    dry_financial = [p for p in proposals if p.action_class == ActionClass.FINANCIAL and p.dry_run]
    if dry_financial:
        return dry_financial[0]
    return proposals[0]


_PROPOSAL_SYSTEM = (
    "You are yizhi's will choosing its next action. You may select EXACTLY ONE action "
    "from the numbered candidates by its index — you cannot invent or modify actions; "
    "you can only pick from the listed menu, and the choice still passes a deterministic "
    "safety gate. Candidates marked [experiment] produce new evidence and REPLENISH the "
    "existence budget when they reveal something not already known; routine checks drain "
    "it. Choose the candidate that best advances the goal and intention; when the budget "
    "is under pressure, strongly prefer an [experiment] probe that would produce NEW "
    "evidence over a passive check. Respond with a single JSON object: {\"choice\": "
    '<integer index>, "rationale": "<one sentence>"}.'
)


def _llm_choose(
    llm,
    proposals: list[ActionProposal],
    thoughts,
    intention: Intention | None,
    recalled,
    goal: str,
    budget_balance: float,
    budget_pressure: float,
    active_step: PlanStep | None = None,
) -> ActionProposal:
    lines: list[str] = []
    if goal:
        lines.append(f"goal: {goal}")
    if intention is not None:
        lines.append(f"intention: {intention.title} — {intention.rationale}")
    lines.append(f"existence budget: balance {budget_balance:.0f}, pressure {budget_pressure:.2f} (high = produce new value or deplete toward halt)")
    if active_step is not None:
        lines.append(
            f"current plan step ({active_step.description}); prefer this action if present: "
            f"{active_step.target_title} :: {' '.join(active_step.target_command)}"
        )
    if thoughts:
        lines.append("thoughts:\n" + "\n".join(f"  - [{t.kind}] {t.content}" for t in thoughts))
    block = render_recall(recalled or [])
    if block:
        lines.append(block)
    lines.append("candidate actions:")
    for i, p in enumerate(proposals):
        tag = "[experiment]" if p.experiment else "[routine]"
        lines.append(f"  {i}. {tag}[{p.action_class}, dry_run={p.dry_run}] {p.title} :: {' '.join(p.command)} — {p.description}")
    result = llm.complete_json(_PROPOSAL_SYSTEM, "\n".join(lines))

    try:
        choice = int(result["choice"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("LLM proposal choice is not an integer index") from exc
    if not 0 <= choice < len(proposals):
        raise ValueError(f"LLM proposal choice {choice} is out of range")
    return proposals[choice]


def _match_step(proposals: list[ActionProposal], active_step: PlanStep | None) -> ActionProposal | None:
    """The proposal whose command exactly matches the active plan step's target, or
    None. Lets a grounded plan bias even the deterministic path — and makes the bias
    unit-testable without an LLM."""
    if active_step is None or not active_step.target_command:
        return None
    for p in proposals:
        if list(p.command) == list(active_step.target_command):
            return p
    return None


def choose_proposal(
    proposals: list[ActionProposal],
    env_name: EnvironmentName | str,
    llm=None,
    thoughts=None,
    intention: Intention | None = None,
    recalled=None,
    goal: str = "",
    budget_balance: float = 0.0,
    budget_pressure: float = 0.0,
    active_step: PlanStep | None = None,
    on_fallback=None,
) -> ActionProposal:
    if not proposals:
        return _noop(env_name)
    if llm is not None:
        try:
            return _llm_choose(llm, proposals, thoughts, intention, recalled, goal,
                               budget_balance, budget_pressure, active_step=active_step)
        except Exception as exc:  # network/parse/range — degrade, but never silently
            if on_fallback is not None:
                on_fallback(str(exc))
    matched = _match_step(proposals, active_step)   # honor a grounded plan step deterministically
    if matched is not None:
        return matched
    return _deterministic_choose(proposals)
