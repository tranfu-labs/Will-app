"""Offline tests for quantitative judgment (P0): the DETERMINISTIC verdict on backtest metrics.

The whole point is that no LLM decides edge-reality — fixed rules do. The headline regression:
a single lucky window (n_entered=1, 100% win) must be judged INSUFFICIENT, never an edge.
"""

from __future__ import annotations

from yizhi.engine.judgment import (
    MIN_ENTERED,
    Verdict,
    judge_backtest,
    judgment_finding,
)


def _m(**kw):
    base = {"n_windows": 100, "n_entered": 50, "total_realized_bps": 0.0, "sharpe_like": 0.0,
            "win_rate": 0.0, "persistence_sign_stability": 0.0, "min_net_bps": 3, "symbol": "X"}
    base.update(kw)
    return base


def test_none_metrics_yield_no_judgment():
    assert judge_backtest(None) is None        # non-backtest action
    assert judge_backtest({}) is None


def test_tiny_sample_is_insufficient_not_an_edge():
    # The headline trap: 1 entered window at 100% win / +56 bps is NOT an edge.
    j = judge_backtest(_m(n_entered=1, total_realized_bps=56.3, win_rate=1.0, sharpe_like=0.0))
    assert j.verdict is Verdict.INSUFFICIENT
    assert "1" in j.reasons[0] and j.verdict not in (Verdict.PROMOTE,)


def test_negative_net_on_a_sufficient_sample_is_kill():
    j = judge_backtest(_m(n_entered=84, total_realized_bps=-1847.2, win_rate=0.0))
    assert j.verdict is Verdict.KILL
    assert j.verdict in (Verdict.PROMOTE, Verdict.KILL)   # KILL is conclusive knowledge


def test_positive_but_weak_is_iterate():
    # Net-positive and well-sampled, but low Sharpe / low persistence -> promising, not proven.
    j = judge_backtest(_m(n_entered=40, total_realized_bps=120.0, sharpe_like=0.2, persistence_sign_stability=0.9))
    assert j.verdict is Verdict.ITERATE
    j2 = judge_backtest(_m(n_entered=40, total_realized_bps=120.0, sharpe_like=0.8, persistence_sign_stability=0.3))
    assert j2.verdict is Verdict.ITERATE         # weak persistence alone also blocks promotion


def test_sized_persistent_risk_adjusted_is_promote():
    j = judge_backtest(_m(n_entered=40, total_realized_bps=578.0, sharpe_like=0.66, win_rate=0.68, persistence_sign_stability=0.7))
    assert j.verdict is Verdict.PROMOTE
    assert 0.0 < j.confidence <= 1.0


def test_sample_gate_precedes_the_net_check():
    # Even a big positive net is INSUFFICIENT if the sample is too small (no false promote).
    j = judge_backtest(_m(n_entered=MIN_ENTERED - 1, total_realized_bps=9999.0, sharpe_like=5.0, persistence_sign_stability=1.0))
    assert j.verdict is Verdict.INSUFFICIENT


def test_judgment_finding_leads_with_the_verdict():
    j = judge_backtest(_m(n_entered=40, total_realized_bps=578.0, sharpe_like=0.66, persistence_sign_stability=0.7, symbol="AERGO"))
    note = judgment_finding(j)
    assert note.startswith("[PROMOTE]") and "AERGO" in note and "n_entered=40" in note
