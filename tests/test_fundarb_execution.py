import json

from yizhi.core.schemas import ActionRecord, ActionStatus, EnvironmentName, VerificationResult
from yizhi.fundarb.execution import execute_experiment_queue


def _queue(tmp_path, command=None):
    queue = {
        "schema_version": 1,
        "source_coverage_id": "cov-1",
        "experiments": [
            {
                "id": "exp-1",
                "status": "queued",
                "priority": 1,
                "symbol": "EDGEY",
                "min_net_bps": 5.0,
                "horizon_hours": 24.0,
                "coverage": {"overlap_points": 20, "snapshot_diff": 0.001},
                "command": command or [
                    "yizhi:arbbot-backtest",
                    "funding_diff",
                    "symbol=EDGEY",
                    "min_net_bps=5",
                    "horizon_hours=24",
                ],
            }
        ],
    }
    path = tmp_path / "queue.json"
    path.write_text(json.dumps(queue), encoding="utf-8")
    return path


class FakeEnv:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def run(self, proposal):
        self.__class__.calls += 1
        return ActionRecord(
            proposal_id=proposal.id,
            environment=EnvironmentName.ARBBOT,
            status=ActionStatus.SUCCEEDED,
            command=proposal.command,
            exit_code=0,
            stdout="ok",
            stderr="",
            metrics={
                "n_windows": 30,
                "n_entered": 25,
                "sharpe_like": 0.8,
                "win_rate": 0.68,
                "max_drawdown_bps": 5.0,
                "total_realized_bps": 120.0,
                "persistence_sign_stability": 0.75,
                "min_net_bps": 5.0,
                "symbol": "EDGEY",
                "calibration_verdict": "ok",
            },
        )

    def verify(self, record):
        return VerificationResult(
            action_record_id=record.id,
            passed=True,
            checks=["exit_code_is_zero"],
            summary="ok",
        )


def test_execute_queue_appends_results_once(monkeypatch, tmp_path):
    from yizhi.fundarb import execution

    FakeEnv.calls = 0
    monkeypatch.setattr(execution, "ArbBotEnvironment", FakeEnv)
    results = tmp_path / "results.jsonl"

    first = execute_experiment_queue(_queue(tmp_path), results, now_iso="2026-06-27T00:00:00+00:00")
    second = execute_experiment_queue(_queue(tmp_path), results, now_iso="2026-06-27T01:00:00+00:00")

    assert first.executed == 1
    assert second.executed == 0
    assert second.skipped == 1
    assert FakeEnv.calls == 1
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["status"] == "succeeded"
    assert rows[0]["judgment"]["verdict"] == "promote"
    assert rows[0]["safety"]["sentinel_only"] is True


def test_execute_queue_fail_closed_on_non_sentinel(monkeypatch, tmp_path):
    from yizhi.fundarb import execution

    FakeEnv.calls = 0
    monkeypatch.setattr(execution, "ArbBotEnvironment", FakeEnv)
    results = tmp_path / "results.jsonl"

    outcome = execute_experiment_queue(_queue(tmp_path, command=["make", "smoke"]), results)

    assert outcome.denied == 1
    assert FakeEnv.calls == 0
    row = json.loads(results.read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == "denied"
    assert "only runs" in row["action"]["error"]


def test_execute_queue_uses_policy_gate_for_invalid_params(monkeypatch, tmp_path):
    from yizhi.fundarb import execution

    FakeEnv.calls = 0
    monkeypatch.setattr(execution, "ArbBotEnvironment", FakeEnv)
    results = tmp_path / "results.jsonl"
    bad = ["yizhi:arbbot-backtest", "funding_diff", "symbol=EDGEY", "min_net_bps=oops"]

    outcome = execute_experiment_queue(_queue(tmp_path, command=bad), results)

    assert outcome.denied == 1
    assert FakeEnv.calls == 0
    row = json.loads(results.read_text(encoding="utf-8").splitlines()[0])
    assert row["policy"]["allowed"] is False
    assert any("structural validation" in reason for reason in row["policy"]["reasons"])


def test_execute_queue_degrades_on_missing_cache(tmp_path):
    results = tmp_path / "results.jsonl"
    outcome = execute_experiment_queue(_queue(tmp_path), results, funding_cache=tmp_path / "missing.json")

    assert outcome.failed == 1
    row = json.loads(results.read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == "failed"
    assert "fetch_funding_via_vps" in row["action"]["stderr"]
