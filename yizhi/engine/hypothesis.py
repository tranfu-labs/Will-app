"""Hypothesis authoring — yizhi AUTHORING a concrete backtest, not picking from a menu.

A2.1 had the environment ENUMERATE the threshold grid (symbol x {enter-all, filter=3}); the
LLM only chose an index. That caps the agent at thresholds the environment foresaw — a
critique proposing min_net_bps=5 had no executable proposal. A2.2 lets the LLM AUTHOR the
parameters: given the universe (cached instruments), the experiment ledger, and any standing
FALSE-NEGATIVE critique note, it proposes ONE concrete spec {symbol, min_net_bps,
horizon_hours} with ANY numeric threshold. The loop turns it into a single authored
ActionProposal — and BOTH walls still hold: the environment builds the command from its own
vocabulary (wall 1: the LLM can only parameterize the backtest the env already declared, not
name a new command) and the policy gate structurally validates the params (wall 2). The
deterministic backtest oracle still renders the verdict; authoring only widens WHAT can be
asked, never who decides truth.

Deterministic default: no LLM -> no authored hypothesis (None), so the loop is unchanged
offline. The symbol is validated against the universe here too, so a hallucinated instrument
never reaches the gate.
"""

from __future__ import annotations

from yizhi.engine.recall_render import render_recall

_AUTHOR_SYSTEM = (
    "You are yizhi authoring ONE concrete funding-diff backtest to run next — you are NOT "
    "picking from a menu, you choose the parameters yourself. Given the tradable universe, the "
    "experiment ledger (what you already found), and any standing FALSE-NEGATIVE note, propose "
    "the single most informative backtest. You choose: the symbol (MUST be one from the "
    "universe), the min_net_bps entry filter (ANY number — a very negative value like -1000 "
    "means enter-all/no filter, a positive value like 3, 5, or 8 admits only higher-quality "
    "windows), and horizon_hours. Prefer a test that resolves an open doubt or probes an "
    "untested threshold over repeating a known result. Respond with one JSON object: "
    '{"symbol": "<symbol from the universe>", "min_net_bps": <number>, "horizon_hours": '
    '<number, e.g. 24>, "rationale": "<one sentence>"}. If nothing is worth testing, return '
    '{"symbol": ""}.'
)


def author_backtest(
    llm,
    universe,
    ledger,
    recalled=None,
    *,
    budget_balance: float = 0.0,
    budget_pressure: float = 0.0,
    on_fallback=None,
) -> dict | None:
    """Author a concrete backtest spec from the universe + ledger + standing critique, or
    None — when the engine is off, the universe is empty, nothing is worth testing (empty or
    out-of-universe symbol), or extraction fails. The returned dict is {symbol, min_net_bps,
    horizon_hours, rationale}; the env then builds the gated command from it. The symbol is
    validated against the universe HERE so a hallucination cannot reach the policy gate."""
    if llm is None or not universe:
        return None
    lines = [f"tradable universe: {', '.join(universe)}"]
    if ledger:
        lines.append("experiment ledger:\n" + "\n".join(f"  - [{s}] {c}" for s, c in ledger))
    block = render_recall(recalled or [])
    if block:
        lines.append(block)
    lines.append(
        f"existence budget: balance {budget_balance:.0f}, pressure {budget_pressure:.2f} "
        "(high = produce new value)"
    )
    try:
        result = llm.complete_json(_AUTHOR_SYSTEM, "\n".join(lines))
        symbol = str(result.get("symbol", "")).strip()
    except Exception as exc:  # network/parse — degrade, but never silently
        if on_fallback is not None:
            on_fallback(str(exc))
        return None
    if not symbol or symbol not in universe:
        return None  # nothing worth testing, or a hallucinated instrument

    def _num(key: str, default: float) -> float:
        try:
            return float(result.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    return {
        "symbol": symbol,
        "min_net_bps": _num("min_net_bps", 3),
        "horizon_hours": _num("horizon_hours", 24),
        "rationale": str(result.get("rationale", "")).strip(),
    }
