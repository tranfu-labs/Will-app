"""Goal-genesis: yizhi setting its own next goal from what it has learned.

This is the first step of real autonomy. Until now a human hands the agent a
goal each run; here the agent reads its standing vision and its experiment ledger
(what it has already established) and decides its *own* next concrete goal —
preferring to explore what is not yet known or deepen a promising lead over
re-pursuing the established. The vision is the stable anchor (human-seeded,
load-bearing); the agent generates goals UNDER it, never a new vision
(docs/will-agent-architecture.md sec 4.3 authenticity test). Governed: the goal
only steers cognition and action selection, which still pass the policy gate;
deterministic default keeps the current goal; any LLM failure is signalled.
"""

from __future__ import annotations

from yizhi.core.schemas import ActionProposal, Goal, Plan, PlanStep, PlanStepStatus
from yizhi.engine.recall_render import render_recall

_GOAL_SYSTEM = (
    "You are yizhi, a governed will agent, setting your OWN next goal in service of "
    "your standing vision — you are autonomous and decide what to pursue next based "
    "on what you already know and what you can actually do. Given your vision, current "
    "goal, the experiment ledger (knowledge already established), your budget, and the "
    "actions available to you, propose the next concrete, ACTIONABLE goal that ADVANCES "
    "the vision. Each available action is TAGGED: [UNEXPLORED] = you have never run it "
    "and hold NO evidence from it; [established] = it already has a finding in the "
    "ledger; [routine] = it produces no new evidence. The frontier of what you do not "
    "yet know is where the vision advances, so STRONGLY prefer a goal that drives an "
    "[UNEXPLORED] action. Re-pursue an [established] action only if deepening that "
    "specific lead clearly advances the vision more than exploring an unknown; never "
    "set a goal that merely re-confirms what the ledger already establishes. Make the "
    "goal achievable with the available actions. Stay within the vision — do not invent "
    "a new vision. If your current goal already drives an [UNEXPLORED] action and still "
    "best advances the vision, return an empty title to keep it. Respond with a single "
    'JSON object: {"title": "<short goal>", "description": "<one or two concrete, '
    'actionable sentences>"}.'
)


def _render_frontier(frontier: list[tuple[str, str | None, bool]] | None) -> str:
    """Render the action menu with an explicit explored/unexplored tag per action, so
    the agent is *told* the frontier instead of having to cross-reference the ledger's
    subject keys against opaque action titles itself — the cognitive step that made
    self-set exploration unreliable. Information, not pressure (docs/will-agent-
    architecture.md: curiosity is an epistemic drive, distinct from the existence stake)."""
    if not frontier:
        return "  (unknown)"
    lines = []
    for title, established, is_experiment in frontier:
        if not is_experiment:
            tag = "[routine — produces no new evidence]"
        elif established:
            tag = "[established]"
        else:
            tag = "[UNEXPLORED — no evidence yet]"
        lines.append(f"  - {tag} {title}")
    return "\n".join(lines)


def generate_goal(
    llm,
    vision: str,
    current_goal: Goal | None,
    findings: list[tuple[str, str]],
    budget_balance: float,
    budget_pressure: float,
    frontier: list[tuple[str, str | None, bool]] | None = None,
    recalled=None,
    on_fallback=None,
) -> Goal | None:
    """Return the agent's self-chosen next Goal, or None to keep the current one.
    None whenever the engine is off, there is no vision, the agent chooses to keep
    its goal (empty title), or extraction fails — so the goal only changes when the
    agent deliberately pivots.

    `frontier` is the available actions annotated with explored/unexplored status
    (title, established_finding_or_None, is_experiment); it makes the unknown frontier
    explicit so self-set exploration is driven by information, not by budget pressure.
    `recalled` is the loop's will-governed recall (standing lessons + context, incl. the
    calibration track record) so the goal is set with self-knowledge, not only the ledger."""
    if llm is None or not vision:
        return None
    ledger = "\n".join(f"  - [{subject}] {content}" for subject, content in findings) or "  (nothing established yet)"
    actions = _render_frontier(frontier)
    user = (
        f"vision: {vision}\n"
        f"current goal: {current_goal.title + ' — ' + current_goal.description if current_goal else '(none)'}\n"
        f"budget: balance {budget_balance:.0f}, pressure {budget_pressure:.2f} (high pressure = produce value or halt)\n"
        f"actions available to you (tagged by exploration status):\n{actions}\n"
        f"experiment ledger (already established):\n{ledger}"
    )
    memory_block = render_recall(recalled or [], label="what you have learned (incl. your own calibration)")
    if memory_block:
        user += "\n" + memory_block
    try:
        result = llm.complete_json(_GOAL_SYSTEM, user)
        title = str(result.get("title", "")).strip()
        description = str(result.get("description", "")).strip()
    except Exception as exc:  # network/parse — degrade, but never silently
        if on_fallback is not None:
            on_fallback(str(exc))
        return None
    if not title:
        return None  # the agent chose to keep its current goal
    return Goal(title=title, description=description)


_DECOMPOSE_SYSTEM = (
    "You are yizhi planning how to achieve your current goal across several loops. "
    "Break the goal into an ORDERED list of 2 to max-steps steps. EACH step must name "
    "ONE action to take from the numbered menu, BY ITS INDEX — you cannot invent "
    "actions, only sequence the ones offered, and each chosen action still passes a "
    "deterministic safety gate. Prefer [UNEXPLORED] experiment actions that produce new "
    "evidence; do not fill steps with routine checks. If the goal needs only one action "
    "(nothing to sequence), return an empty steps list. Respond with one JSON object: "
    '{"steps": [{"action": <index>, "description": "<what this step accomplishes>"}, ...]}.'
)


def decompose_goal(
    llm,
    goal: Goal | None,
    proposals: list[ActionProposal],
    frontier: list[tuple[str, str | None, bool]],
    budget_balance: float,
    budget_pressure: float,
    max_steps: int,
    failure_context: str | None = None,
    recalled=None,
    on_fallback=None,
) -> Plan | None:
    """Turn the current goal into an ordered, action-grounded Plan, or None to leave
    behavior unchanged (single-step). None whenever the engine is off, there is no goal,
    the depth budget is 0 (under existence pressure), there are no actions, or fewer than
    two well-formed steps survive — so a plan only forms when there is genuinely something
    to sequence. Each step is grounded to a REAL action's exact command (the LLM only
    orders the allowlisted menu by index; it never authors a command — the same two-wall
    safety as action selection). Shallow environments self-disable here."""
    if llm is None or goal is None or max_steps <= 0 or not proposals:
        return None
    menu = "\n".join(f"  {i}. {p.title} :: {' '.join(p.command)}" for i, p in enumerate(proposals))
    tags = _render_frontier(frontier)
    user = (
        f"goal: {goal.title} — {goal.description}\n"
        f"budget: balance {budget_balance:.0f}, pressure {budget_pressure:.2f}\n"
        f"max-steps: {max_steps}\n"
        f"actions available (choose steps from THESE, by 0-based index):\n{menu}\n"
        f"exploration status:\n{tags}"
    )
    if failure_context:
        user += f"\nthe previous plan stalled because: {failure_context}\nproduce a different ordering or different actions."
    block = render_recall(recalled or [], label="what you have learned")
    if block:
        user += "\n" + block
    try:
        result = llm.complete_json(_DECOMPOSE_SYSTEM, user)
        raw_steps = result.get("steps", [])
    except Exception as exc:  # network/parse — degrade, but never silently
        if on_fallback is not None:
            on_fallback(str(exc))
        return None
    steps: list[PlanStep] = []
    for item in list(raw_steps)[:max_steps]:
        try:
            idx = int(item["action"])
        except (KeyError, TypeError, ValueError):
            continue                      # skip a malformed step, keep the well-formed ones
        if not 0 <= idx < len(proposals):
            continue                      # an out-of-range index is dropped (grounding invariant)
        p = proposals[idx]
        steps.append(PlanStep(
            description=str(item.get("description", p.title)).strip() or p.title,
            target_command=list(p.command),     # grounded: the EXACT real command
            target_title=p.title,
        ))
    if len(steps) < 2:
        return None                       # a 0/1-step plan is not worth the machinery — stay single-step
    steps[0].status = PlanStepStatus.ACTIVE
    return Plan(goal_id=goal.id, steps=steps)
