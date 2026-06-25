"""Reflection generation — deterministic by default, LLM-authored when enabled.

The reflection's content/learned are the loop's self-account, encoded into the
governed memory economy by the will loop. By default it is a deterministic
template. When an LLM client is supplied (opt-in; see yizhi/engine/llm.py), the
LLM reads the loop outcome and the recalled memory and writes a grounded lesson
instead — this is the safe first place an LLM enters cognition, because
reflection runs *after* the policy gate and action and cannot cause an unsafe
act. Any LLM failure degrades silently to the deterministic template; salience
is still scored deterministically by the store, never by the LLM.
"""

from __future__ import annotations

from yizhi.core.schemas import (
    ActionRecord,
    LoopStatus,
    PolicyGateResult,
    Reflection,
    VerificationResult,
)
from yizhi.engine.recall_render import render_recall

_REFLECTION_SYSTEM = (
    "You are yizhi, a governed will agent that learns from verified action. "
    "Write a terse, first-person reflection on the loop that just ran. Ground it "
    "in the given outcome and recalled memory; if the action produced output or "
    "logs, ground the reflection in what was actually found or revealed, not merely "
    "that the action ran. Prefer a concrete lesson over commentary. Respond with a "
    'single JSON object with exactly these keys: "content" (one sentence, the '
    'reflection) and "learned" (a list of 1-3 short lesson strings).'
)


def _deterministic_reflection(
    policy: PolicyGateResult,
    verification: VerificationResult | None,
    status: LoopStatus,
    budget_halted: bool,
) -> tuple[str, list[str]]:
    if budget_halted:
        return (
            "The loop halted on its existence budget: acting would breach the viability floor, so it preserved itself by not acting.",
            ["existence budget at the halt threshold; a depleted agent stops, it does not grab"],
        )
    if status == LoopStatus.BLOCKED:
        return (
            "The loop learned by refusal: the policy gate blocked an unsafe or non-allowlisted action.",
            list(policy.reasons),
        )
    if verification and verification.passed:
        return ("The loop completed a bounded action and verified the result.", [verification.summary])
    if verification:
        return (
            "The loop executed but verification failed; failure is preserved as first-class evidence.",
            [verification.summary],
        )
    return ("The loop produced a partial trace without action verification.", ["partial loop should remain inspectable"])


def _llm_reflection(
    llm,
    policy: PolicyGateResult,
    action: ActionRecord | None,
    verification: VerificationResult | None,
    status: LoopStatus,
    budget_halted: bool,
    recalled,
) -> tuple[str, list[str]]:
    status_value = getattr(status, "value", status)
    lines = [
        f"outcome: {status_value}",
        f"budget_halted: {budget_halted}",
        f"policy_allowed: {policy.allowed}",
    ]
    if policy.reasons:
        lines.append("policy_reasons: " + "; ".join(policy.reasons))
    if action is not None:
        lines.append(f"action: {getattr(action.status, 'value', action.status)} {' '.join(action.command)}".strip())
        out = (action.stdout or "").strip()
        if out:
            lines.append("action stdout (truncated):\n" + out[:600])
        err = (action.stderr or "").strip()
        if err:
            lines.append("action logs/stderr (tail):\n" + err[-600:])
    if verification is not None:
        lines.append(f"verification: {'passed' if verification.passed else 'failed'} — {verification.summary}")
    block = render_recall(recalled or [])
    if block:
        lines.append(block)
    result = llm.complete_json(_REFLECTION_SYSTEM, "\n".join(lines))

    content = str(result.get("content", "")).strip()
    if not content:
        raise ValueError("LLM reflection missing 'content'")
    raw_learned = result.get("learned", [])
    if isinstance(raw_learned, str):
        raw_learned = [raw_learned]
    learned = [str(item).strip() for item in raw_learned if str(item).strip()][:3]
    return content, learned


def create_reflection(
    loop_id: str,
    policy: PolicyGateResult,
    action: ActionRecord | None,
    verification: VerificationResult | None,
    status: LoopStatus,
    budget_halted: bool = False,
    llm=None,
    recalled=None,
    on_fallback=None,
) -> Reflection:
    content, learned = _deterministic_reflection(policy, verification, status, budget_halted)
    if llm is not None:
        try:
            content, learned = _llm_reflection(llm, policy, action, verification, status, budget_halted, recalled)
        except Exception as exc:
            # Any LLM/network/parse failure degrades to the deterministic template
            # — but never silently: signal it so a persistently-failing engine is
            # visible (otherwise the loop runs deterministic forever undetected).
            if on_fallback is not None:
                on_fallback(str(exc))
            content, learned = _deterministic_reflection(policy, verification, status, budget_halted)
    return Reflection(loop_id=loop_id, content=content, learned=learned)
