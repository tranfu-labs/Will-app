import json

from yizhi.core.schemas import ActionClass, ActionProposal, EnvironmentName
from yizhi.fundarb.experiments import build_experiment_queue, write_experiment_queue
from yizhi.policy.gates import run_policy_gate


def _write_coverage(tmp_path):
    coverage = {
        "schema_version": 1,
        "min_periods": 3,
        "records": 14,
        "symbols": 3,
        "symbol_coverage": {
            "EDGEY": {
                "backtest_ready": True,
                "overlap_points": 5,
                "overlap_start": "2026-01-01T00:00:00+00:00",
                "overlap_end": "2026-01-02T00:00:00+00:00",
                "snapshot_diff": 0.001,
            },
            "MID": {
                "backtest_ready": True,
                "overlap_points": 4,
                "overlap_start": "2026-01-01T00:00:00+00:00",
                "overlap_end": "2026-01-02T00:00:00+00:00",
                "snapshot_diff": -0.0005,
            },
            "THIN": {
                "backtest_ready": False,
                "overlap_points": 1,
                "snapshot_diff": 0.01,
            },
        },
    }
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(coverage), encoding="utf-8")
    return path


def _proposal(command):
    return ActionProposal(
        environment=EnvironmentName.ARBBOT,
        action_class=ActionClass.FINANCIAL,
        title="queued experiment",
        command=command,
        dry_run=True,
    )


def test_build_experiment_queue_from_coverage(tmp_path):
    queue = build_experiment_queue(
        _write_coverage(tmp_path),
        min_net_bps=[-1000, 3],
        horizon_hours=[24, 48],
    )

    assert queue["symbols"] == 2
    assert len(queue["experiments"]) == 8
    assert [item["symbol"] for item in queue["experiments"][:4]] == ["EDGEY"] * 4
    assert {item["symbol"] for item in queue["experiments"]} == {"EDGEY", "MID"}
    assert all(item["status"] == "queued" for item in queue["experiments"])
    assert all(item["command"][0:2] == ["yizhi:arbbot-backtest", "funding_diff"] for item in queue["experiments"])
    assert len({item["id"] for item in queue["experiments"]}) == 8


def test_queued_commands_pass_arbbot_policy_gate_and_write_json(tmp_path):
    queue = build_experiment_queue(
        _write_coverage(tmp_path),
        min_net_bps=[-1000, 5],
        horizon_hours=[24],
        max_symbols=1,
    )
    path = write_experiment_queue(queue, tmp_path / "queue.json")
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["symbols"] == 1
    assert len(saved["experiments"]) == 2
    for item in saved["experiments"]:
        assert run_policy_gate(_proposal(item["command"])).allowed


def test_queue_write_preserves_generated_at_when_stable(tmp_path):
    output = tmp_path / "queue.json"
    first = build_experiment_queue(_write_coverage(tmp_path), min_net_bps=[3], horizon_hours=[24], max_symbols=1)
    first["generated_at"] = "first"
    write_experiment_queue(first, output)

    second = dict(first)
    second["generated_at"] = "second"
    write_experiment_queue(second, output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["generated_at"] == "first"

    changed = build_experiment_queue(_write_coverage(tmp_path), min_net_bps=[3, 5], horizon_hours=[24], max_symbols=1)
    changed["generated_at"] = "third"
    write_experiment_queue(changed, output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["generated_at"] == "third"
