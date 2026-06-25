"""Critique faculty — yizhi questioning its own conclusions to find FALSE NEGATIVES.

Research is settled (Huang et al., ICLR 2024; CRITIC, Gou et al.): an LLM cannot
reliably self-correct *reasoning* by introspection — critique must be grounded in an
EXTERNAL ORACLE. yizhi's oracle is its own deterministic backtest probe. So this
faculty does NOT decide truth; it *generates a doubt* and proposes a concrete RE-TEST
(a backtest with different params/instrument). The deterministic backtest then renders
the verdict. The classic example it must catch: ArbBot's "funding-diff has no edge" was
a false negative from only testing mainstream / entering all windows — the edge lives in
the long tail and survives only with a min_net_bps filter (docs/data-via-vps.md).

Deterministic default: no LLM -> no critique (None), so the loop is unchanged offline.
"""

from __future__ import annotations

_CRITIQUE_SYSTEM = (
    "You are yizhi critically examining your OWN backtest findings to find a FALSE NEGATIVE "
    "— an edge you may have wrongly dismissed. You CANNOT decide truth by reasoning; you can "
    "only propose ONE concrete re-test that the deterministic backtest ORACLE will verify. "
    "Look at the findings for a result dismissed as 'no edge'/loss that might be wrong because: "
    "(1) only enter-all (min_net_bps very negative) was tested — a positive min_net_bps filter "
    "may isolate the profitable windows; (2) the cross-venue funding diff is persistent (high "
    "sign-stability) yet the backtest lost — a filtered re-test is warranted; (3) an instrument "
    "with a large funding diff was not tested. Propose the single most promising re-test. Use a "
    "symbol that appears in the findings. Respond with one JSON object: "
    '{"doubt": "<one sentence on why this may be a false negative>", '
    '"retest_symbol": "<symbol>", "retest_min_net_bps": <number, e.g. 3>}. '
    'If no finding looks like a false negative, return {"doubt": ""}.'
)


def generate_critique(llm, findings: list[tuple[str, str]], on_fallback=None) -> dict | None:
    """Examine the experiment ledger for a likely false negative and propose a re-test, or
    None. None whenever the engine is off, there are no findings, the agent finds nothing to
    doubt (empty doubt), or extraction fails — so a critique is raised only when warranted.
    The returned dict is `{doubt, retest_symbol, retest_min_net_bps}`; the loop turns it into
    a standing memory that biases the next action toward the re-test, which the ORACLE judges."""
    if llm is None or not findings:
        return None
    ledger = "\n".join(f"  - [{subject}] {content}" for subject, content in findings)
    try:
        result = llm.complete_json(_CRITIQUE_SYSTEM, f"findings:\n{ledger}")
        doubt = str(result.get("doubt", "")).strip()
        symbol = str(result.get("retest_symbol", "")).strip()
    except Exception as exc:  # network/parse — degrade, but never silently
        if on_fallback is not None:
            on_fallback(str(exc))
        return None
    if not doubt or not symbol:
        return None  # nothing looked like a false negative
    try:
        min_net = float(result.get("retest_min_net_bps", 3))
    except (TypeError, ValueError):
        min_net = 3.0
    return {"doubt": doubt, "retest_symbol": symbol, "retest_min_net_bps": min_net}


def critique_memory(critique: dict) -> str:
    """The standing self-knowledge a critique leaves behind: a high-salience prompt to
    re-test a suspected false negative. It surfaces in standing recall so the next loop's
    action selection is biased toward the filtered re-test the ORACLE will then judge."""
    return (
        f"FALSE-NEGATIVE SUSPECT — re-test {critique['retest_symbol']} with a funding filter "
        f"(min_net_bps={critique['retest_min_net_bps']:g}) to verify the dismissal: {critique['doubt']}"
    )
