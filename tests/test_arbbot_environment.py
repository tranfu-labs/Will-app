from pathlib import Path

import pytest

from yizhi.core.schemas import ActionStatus, WillState
from yizhi.environments.arbbot import ArbBotEnvironment
from yizhi.policy.gates import run_policy_gate


ARBBOT_ROOT = Path("/Users/griffith/Projects/AI/ArbBot")


def test_arbbot_observes_safety_facts_when_present():
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    observations = ArbBotEnvironment(ARBBOT_ROOT).observe()
    facts = {obs.source: obs.facts for obs in observations}
    assert "status" in facts["arbbot.git_status"]
    assert facts["arbbot.phase_gate"]["phase_4_paper_gate"] is True
    assert facts["arbbot.safety_boundary"]["no_api_secrets"] is True
    assert facts["arbbot.makefile"]["has_smoke"] is True


def test_arbbot_proposals_are_policy_checked():
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    proposals = ArbBotEnvironment(ARBBOT_ROOT).propose_actions(WillState())
    commands = [proposal.command for proposal in proposals]
    assert ["make", "smoke"] in commands
    assert ["make", "test"] in commands  # the offline-test probe (strategy/backtest engine health)
    assert ["git", "status", "--short", "--branch"] in commands
    for proposal in proposals:
        assert run_policy_gate(proposal).allowed


def test_arbbot_marks_only_real_probes_as_experiments():
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    by_cmd = {tuple(p.command): p.experiment for p in ArbBotEnvironment(ARBBOT_ROOT).propose_actions(WillState())}
    # genuine evidence-producing probes earn the ledger + replenishment
    assert by_cmd[("make", "smoke")] is True
    assert by_cmd[("make", "test")] is True
    assert by_cmd[("python", "scripts/smoke_funding_diff_scan.py", "--dry-run")] is True
    # routine checks do not — they neither pollute the ledger nor pay
    assert by_cmd[("git", "status", "--short", "--branch")] is False
    assert by_cmd[("make", "safety")] is False


def test_arbbot_backtest_probe_returns_real_metrics(tmp_path):
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    env = ArbBotEnvironment(ARBBOT_ROOT, funding_cache=_write_fixture_cache(tmp_path))
    probe = next(p for p in env.propose_actions(WillState()) if p.command and p.command[0] == "yizhi:arbbot-backtest")
    assert probe.experiment is True
    # the probe passes the policy gate (second wall, structural) — it can actually run
    assert run_policy_gate(probe).allowed is True
    record = env.run(probe)                                    # in-process, no subprocess/network
    assert record.exit_code == 0 and record.status == ActionStatus.SUCCEEDED.value
    # real quant evidence is in stdout for findings to extract
    for token in ("sharpe_like=", "win_rate=", "total_realized_bps=", "calibration_verdict=", "n_entered="):
        assert token in record.stdout
    assert env.verify(record).passed is True


def _tok(stdout: str, key: str) -> str:
    return next(t.split("=", 1)[1] for t in stdout.split() if t.startswith(key + "="))


def _write_fixture_cache(tmp_path):
    # A deterministic fixture so the real-data PATH is tested without live network / VPS:
    # EDGEY has a big persistent cross-venue diff (binance >> bybit, constant -> sign-stable);
    # FLAT has ~no diff. Real funding values, 8h interval, 20 periods.
    import json

    ts0, step = 1700000000000, 28800000

    def series(rate, n=20):
        return {str(ts0 + i * step): str(rate) for i in range(n)}

    cache = {"venues": ["binance", "bybit"], "symbols": {
        "EDGEY": {"interval_hours": 8, "snapshot_diff": 0.0009, "binance": series("0.001"), "bybit": series("0.0001")},
        "FLAT": {"interval_hours": 8, "snapshot_diff": 0.0, "binance": series("0.0001"), "bybit": series("0.0001")},
    }}
    path = tmp_path / "funding_cache.json"
    path.write_text(json.dumps(cache))
    return path


def test_arbbot_backtest_uses_real_cached_data_and_reports_persistence(tmp_path):
    # The probe reads the VPS-fetched funding cache and runs ArbBot's REAL backtest (no
    # synthetic data) — one proposal per cached instrument, structurally gated, with a
    # persistence (sign-stability) signal so an edge can be told from snapshot noise.
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    env = ArbBotEnvironment(ARBBOT_ROOT, funding_cache=_write_fixture_cache(tmp_path))
    grid = [p for p in env.propose_actions(WillState()) if p.command and p.command[0] == "yizhi:arbbot-backtest"]
    assert {next(a.split("=")[1] for a in p.command if a.startswith("symbol=")) for p in grid} == {"EDGEY", "FLAT"}
    assert all(run_policy_gate(p).allowed for p in grid)                 # structural gate (parameterized authoring)
    by_symbol = {next(a.split("=")[1] for a in p.command if a.startswith("symbol=")): env.run(p) for p in grid}
    edgey = by_symbol["EDGEY"]
    assert edgey.exit_code == 0
    for token in ("sharpe_like=", "total_realized_bps=", "calibration_verdict=", "persistence_sign_stability="):
        assert token in edgey.stdout
    assert float(_tok(edgey.stdout, "persistence_sign_stability")) == 1.0   # constant diff -> fully sign-stable
    # EDGEY's fat persistent funding diff captures more than FLAT's ~zero diff
    assert float(_tok(edgey.stdout, "total_realized_bps")) > float(_tok(by_symbol["FLAT"].stdout, "total_realized_bps"))


def test_arbbot_backtest_degrades_without_cache(tmp_path):
    # No cached data (e.g. fetch never run) -> a clean failure telling the operator to fetch,
    # never a crash. The probe must not require the live VPS at loop time.
    if not ARBBOT_ROOT.exists():
        pytest.skip("ArbBot repo not present")
    env = ArbBotEnvironment(ARBBOT_ROOT, funding_cache=tmp_path / "absent.json")
    from yizhi.environments.arbbot import BACKTEST_SENTINEL
    from yizhi.core.schemas import ActionProposal, ActionClass, EnvironmentName

    probe = ActionProposal(environment=EnvironmentName.ARBBOT, action_class=ActionClass.FINANCIAL,
                           title="bt", command=[BACKTEST_SENTINEL, "funding_diff", "symbol=NOPE"], dry_run=True)
    rec = env.run(probe)
    assert rec.exit_code == 1 and "fetch_funding_via_vps" in rec.stderr
