"""Quantitative judgment — the DETERMINISTIC verdict on a backtest.

The critique/hypothesis faculties are LLM-formed; the backtest is a deterministic oracle —
but until now its output was just numbers, and findings.py asked the LLM to *interpret* them.
That let a single lucky window (n_entered=1, "100% win") be recorded as an edge. Judgment
closes the loop: it turns structured backtest metrics into a verdict by FIXED rules, so the
question "is this a real, sized, fee-surviving, persistent edge?" is never hallucinated.

This is the project's philosophy applied to evidence: the LLM PROPOSES what to test
(hypothesis) and what to doubt (critique); the deterministic core JUDGES the result. The
verdict then grounds the ledger finding and gates the existence budget — only conclusive
knowledge (a confirmed edge or a confirmed dead end) pays, so the economy stops rewarding
noise.

Verdicts:
  INSUFFICIENT — too few entered windows to conclude anything (the n=1 trap).
  KILL         — net <= 0 after fees on a sufficient sample: a confirmed dead end (real knowledge).
  ITERATE      — net-positive but weak (low Sharpe / low persistence): promising, not proven.
  PROMOTE      — net-positive, sized, persistent, and risk-adjusted: a candidate edge.

Thresholds are deliberately conservative and documented; tighten them as evidence accrues.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

MIN_ENTERED = 20          # below this, a backtest result is noise, not evidence
MIN_SHARPE = 0.5          # risk-adjusted return floor for a promotable edge
MIN_PERSISTENCE = 0.6     # cross-venue funding-diff sign-stability floor (durable, not a blip)
MIN_NET_BPS = 0.0         # must be net-positive AFTER fees


class Verdict(str, Enum):
    INSUFFICIENT = "insufficient"
    KILL = "kill"
    ITERATE = "iterate"
    PROMOTE = "promote"


CONCLUSIVE = (Verdict.PROMOTE, Verdict.KILL)   # the verdicts that are genuine knowledge


@dataclass
class Judgment:
    verdict: Verdict
    confidence: float          # 0..1 heuristic: how firmly the rule fired
    reasons: list[str]
    metrics: dict


def judge_backtest(metrics: dict | None) -> Judgment | None:
    """Render a deterministic verdict on backtest metrics, or None if there are none (e.g. a
    non-backtest action). The sample-size gate is checked FIRST: no statistical claim — edge
    OR no-edge — can be made from too few entered windows, so n_entered=1 is INSUFFICIENT, not
    a 100%-win edge. The verdict is grounded purely in the numbers; it cannot be argued with."""
    if not metrics:
        return None
    n_entered = float(metrics.get("n_entered", 0) or 0)
    n_windows = float(metrics.get("n_windows", 0) or 0)
    net = float(metrics.get("total_realized_bps", 0) or 0)
    sharpe = float(metrics.get("sharpe_like", 0) or 0)
    persistence = float(metrics.get("persistence_sign_stability", 0) or 0)

    # 1. Sample-size gate FIRST — cannot conclude anything from too few entered windows.
    if n_entered < MIN_ENTERED:
        return Judgment(
            Verdict.INSUFFICIENT,
            confidence=min(1.0, n_entered / MIN_ENTERED),
            reasons=[f"only {n_entered:g} entered windows (< {MIN_ENTERED}) — not enough to conclude; widen the sample"],
            metrics=metrics,
        )
    # 2. Net <= 0 after fees on a sufficient sample — a CONFIRMED dead end (real knowledge).
    if net <= MIN_NET_BPS:
        return Judgment(
            Verdict.KILL,
            confidence=min(1.0, n_entered / (2 * MIN_ENTERED)),
            reasons=[f"net {net:+.1f} bps after fees over {n_entered:g} windows — no edge at this threshold"],
            metrics=metrics,
        )
    # 3. Net-positive but weak — promising, not proven.
    weak: list[str] = []
    if sharpe < MIN_SHARPE:
        weak.append(f"sharpe {sharpe:.2f} < {MIN_SHARPE}")
    if persistence < MIN_PERSISTENCE:
        weak.append(f"persistence {persistence:.2f} < {MIN_PERSISTENCE}")
    if weak:
        return Judgment(
            Verdict.ITERATE,
            confidence=0.5,
            reasons=[f"net +{net:.1f} bps but " + "; ".join(weak) + " — tune the threshold or widen the sample"],
            metrics=metrics,
        )
    # 4. Net-positive, sized, persistent, risk-adjusted — a candidate edge.
    return Judgment(
        Verdict.PROMOTE,
        confidence=min(1.0, 0.6 + min(sharpe, 2.0) / 5 + (n_entered - MIN_ENTERED) / 200),
        reasons=[f"net +{net:.1f} bps, sharpe {sharpe:.2f}, persistence {persistence:.2f} over {n_entered:g}/{n_windows:g} windows — candidate edge"],
        metrics=metrics,
    )


def judgment_finding(j: Judgment) -> str:
    """The ledger finding for a judged backtest: the deterministic VERDICT leads, so the
    experiment ledger records verdicts (not an LLM's reading of raw stdout) and the critique
    faculty can question an INSUFFICIENT (get more sample) distinctly from a KILL (truly dead)."""
    m = j.metrics
    sym = m.get("symbol", "?")
    return (
        f"[{j.verdict.value.upper()}] {sym} funding-diff @ min_net_bps={float(m.get('min_net_bps', 0)):g}: "
        f"net {float(m.get('total_realized_bps', 0)):+.1f} bps, win {float(m.get('win_rate', 0)):.0%}, "
        f"sharpe {float(m.get('sharpe_like', 0)):.2f}, persistence {float(m.get('persistence_sign_stability', 0)):.2f}, "
        f"n_entered={float(m.get('n_entered', 0)):g}/{float(m.get('n_windows', 0)):g} — {'; '.join(j.reasons)}"
    )
