"""Offline tests for the calibration loop (predict -> verify -> score).

The prediction is LLM-formed (tested with a FakeLLM); the scoring is deterministic
(Brier over an objective outcome), so it is tested directly. No network.
"""

from __future__ import annotations

from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName
from yizhi.engine.calibration import brier, predict_value, summarize_calibration


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system, user):
        return self.payload


def _experiment():
    return ActionProposal(environment=EnvironmentName.ARBBOT, action_class=ActionClass.FINANCIAL,
                          title="scan", command=["make", "smoke"], dry_run=True, experiment=True)


def _routine():
    return ActionProposal(environment=EnvironmentName.ARBBOT, action_class=ActionClass.INTERNAL,
                          title="git status", command=["git", "status"], dry_run=True, experiment=False)


def test_predict_value_only_for_experiments_with_llm():
    llm = FakeLLM({"confidence": 0.8, "rationale": "fresh probe"})
    assert predict_value(llm, _experiment(), recalled=[]) == 0.8
    assert predict_value(llm, _routine(), recalled=[]) is None   # not an experiment
    assert predict_value(None, _experiment(), recalled=[]) is None  # engine off


def test_predict_value_clamps_and_degrades():
    assert predict_value(FakeLLM({"confidence": 5.0}), _experiment(), recalled=[]) == 1.0

    class Boom:
        def complete_json(self, system, user):
            raise RuntimeError("down")

    seen = []
    assert predict_value(Boom(), _experiment(), recalled=[], on_fallback=seen.append) is None
    assert seen and "down" in seen[0]


def test_brier_score():
    assert brier(1.0, 1.0) == 0.0      # confident and right -> perfect
    assert brier(0.0, 1.0) == 1.0      # confident and wrong -> worst
    assert brier(0.5, 1.0) == 0.25


def test_summarize_calibration_track_record():
    assert "no scored predictions" in summarize_calibration([])
    scored = [
        {"confidence": 0.9, "outcome": 1.0, "brier": brier(0.9, 1.0)},   # confident, right (hit)
        {"confidence": 0.8, "outcome": 0.0, "brier": brier(0.8, 0.0)},   # confident, wrong (miss)
    ]
    summary = summarize_calibration(scored)
    assert "over 2 predictions" in summary
    assert "hit-rate 1/2" in summary  # one directional hit
