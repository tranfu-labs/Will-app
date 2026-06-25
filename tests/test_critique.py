"""Offline tests for the critique faculty (question false negatives -> propose a re-test).

The critique is LLM-formed (FakeLLM here); it never decides truth — it proposes a
re-test the deterministic backtest oracle verifies. No network.
"""

from __future__ import annotations

from yizhi.engine.critique import critique_memory, generate_critique

_FINDINGS = [
    ("arbbot/probe/btc", "BTC funding_diff entered all windows and lost -1847 bps, 0% win"),
    ("arbbot/probe/alice", "ALICE: persistent cross-venue diff (sign-stability 0.84) but enter-all lost -625 bps"),
]


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system, user):
        self.calls.append((system, user))
        return self.payload


def test_generate_critique_proposes_a_grounded_retest():
    llm = FakeLLM({"doubt": "ALICE diff is persistent yet dismissed at enter-all", "retest_symbol": "ALICE", "retest_min_net_bps": 3})
    crit = generate_critique(llm, _FINDINGS)
    assert crit == {"doubt": "ALICE diff is persistent yet dismissed at enter-all", "retest_symbol": "ALICE", "retest_min_net_bps": 3.0}
    # the findings ground the prompt
    assert "ALICE" in llm.calls[0][1] and "BTC" in llm.calls[0][1]


def test_generate_critique_none_when_nothing_to_doubt():
    assert generate_critique(FakeLLM({"doubt": ""}), _FINDINGS) is None            # empty doubt
    assert generate_critique(FakeLLM({"doubt": "x", "retest_symbol": ""}), _FINDINGS) is None  # no symbol


def test_generate_critique_none_without_llm_or_findings():
    assert generate_critique(None, _FINDINGS) is None                              # engine off
    assert generate_critique(FakeLLM({"doubt": "x", "retest_symbol": "ALICE"}), []) is None  # nothing tried yet


def test_generate_critique_degrades_and_signals_on_error():
    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("critique down")

    seen: list[str] = []
    assert generate_critique(Boom(), _FINDINGS, on_fallback=seen.append) is None
    assert seen and "critique down" in seen[0]


def test_generate_critique_defaults_bad_threshold():
    crit = generate_critique(FakeLLM({"doubt": "d", "retest_symbol": "ALICE", "retest_min_net_bps": "oops"}), _FINDINGS)
    assert crit["retest_min_net_bps"] == 3.0   # non-numeric -> sane default


def test_critique_memory_is_a_retest_directive():
    note = critique_memory({"doubt": "persistent yet dismissed", "retest_symbol": "ALICE", "retest_min_net_bps": 3.0})
    assert "FALSE-NEGATIVE SUSPECT" in note and "ALICE" in note and "min_net_bps=3" in note
