"""Offline tests for hypothesis authoring (A2.2): the LLM AUTHORS backtest parameters
(a self-chosen threshold), the env builds the gated command from them, and BOTH walls hold.

LLM-formed (FakeLLM here); the deterministic backtest oracle still renders the verdict. The
symbol is validated against the universe so a hallucinated instrument never reaches the gate.
No network.
"""

from __future__ import annotations

from yizhi.engine.hypothesis import author_backtest
from yizhi.environments.arbbot import ArbBotEnvironment
from yizhi.policy.gates import run_policy_gate

_UNIVERSE = ["BTC", "ALICE", "AERGO"]
_LEDGER = [("arbbot/probe/aergo", "AERGO enter-all lost -88 bps, 40% win — but diff is persistent")]


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system, user):
        self.calls.append((system, user))
        return self.payload


def test_author_backtest_authors_a_free_threshold():
    llm = FakeLLM({"symbol": "AERGO", "min_net_bps": 5, "horizon_hours": 24, "rationale": "persistent diff dismissed at enter-all"})
    spec = author_backtest(llm, _UNIVERSE, _LEDGER)
    assert spec == {"symbol": "AERGO", "min_net_bps": 5.0, "horizon_hours": 24.0, "rationale": "persistent diff dismissed at enter-all"}
    # the universe + ledger ground the prompt
    assert "AERGO" in llm.calls[0][1] and "persistent" in llm.calls[0][1]


def test_author_backtest_rejects_hallucinated_symbol():
    # A symbol outside the universe must never reach the gate.
    assert author_backtest(FakeLLM({"symbol": "FAKECOIN", "min_net_bps": 3}), _UNIVERSE, _LEDGER) is None


def test_author_backtest_none_without_llm_or_universe():
    assert author_backtest(None, _UNIVERSE, _LEDGER) is None          # engine off
    assert author_backtest(FakeLLM({"symbol": "BTC"}), [], _LEDGER) is None  # no universe
    assert author_backtest(FakeLLM({"symbol": ""}), _UNIVERSE, _LEDGER) is None  # nothing worth testing


def test_author_backtest_degrades_and_signals_on_error():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("author down")

    seen: list[str] = []
    assert author_backtest(Boom(), _UNIVERSE, _LEDGER, on_fallback=seen.append) is None
    assert seen and "author down" in seen[0]


def test_author_backtest_defaults_bad_numerics():
    spec = author_backtest(FakeLLM({"symbol": "BTC", "min_net_bps": "oops", "horizon_hours": None}), _UNIVERSE, _LEDGER)
    assert spec["min_net_bps"] == 3.0 and spec["horizon_hours"] == 24.0   # sane defaults, never crash


def test_authored_backtest_builds_a_gate_passing_command():
    # The env assembles the command from its own vocabulary (wall 1); the gate validates the
    # authored params structurally (wall 2). An env-never-enumerated threshold (7.5) passes.
    env = ArbBotEnvironment()
    proposal = env.authored_backtest({"symbol": "AERGO", "min_net_bps": 7.5, "horizon_hours": 24, "rationale": "r"})
    assert proposal.command == ["yizhi:arbbot-backtest", "funding_diff", "symbol=AERGO", "min_net_bps=7.5", "horizon_hours=24"]
    assert proposal.experiment is True
    assert run_policy_gate(proposal).allowed is True                 # both walls pass on an authored threshold
