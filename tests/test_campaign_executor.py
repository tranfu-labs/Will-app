from __future__ import annotations

import json
from pathlib import Path

from yizhi.campaigns.btc import build_btc_campaign
from yizhi.campaigns.engine import campaign_tick
from yizhi.campaigns.executor import (
    BacktestTaskRunExecutor,
    DelegationTaskRunExecutor,
    FakeTaskRunExecutor,
    KindRoutingExecutor,
    resolve_executor,
)
from yizhi.campaigns.schemas import CampaignStatus, TaskRunKind
from yizhi.core.schemas import DelegationReport, DelegationTask, EventType
from yizhi.engine.delegation import FakeDelegationClient
from yizhi.state.store import init_db, list_events


class ContractFakeClient:
    """Offline worker that honors the artifact contract: it reads the required
    `## slug` headings out of the instruction and returns a compliant report."""

    def __init__(self, *, leak_secret: bool = False) -> None:
        self.leak_secret = leak_secret
        self.tasks: list[DelegationTask] = []

    def run(self, task: DelegationTask) -> DelegationReport:
        self.tasks.append(task)
        headings = [line for line in task.instruction.splitlines() if line.startswith("## ")]
        lines = ["# 研究报告", ""]
        for heading in headings:
            lines.append(heading)
            lines.append("")
            if heading.strip().lower() == "## sources":
                lines.append("- https://bitcoin.org/bitcoin.pdf")
            else:
                lines.append("真实研究内容占位(离线合同测试)。")
            lines.append("")
        if self.leak_secret:
            lines.append("apikey=sk_live_abcdef123456")
        return DelegationReport(task_id=task.id, ok=True, summary="contract worker", output_text="\n".join(lines))


def _packet_fixture(tmp_path):
    funding = tmp_path / "funding"
    funding.mkdir()
    packet = {
        "packet_id": "testpacket",
        "rule_version": "judgment-v1",
        "generated_at": "2026-07-03T00:00:00+00:00",
        "source_coverage_id": "cov1",
        "source_results_path": "results.jsonl",
        "safety": {"live_trading_authorized": False, "network_required": False, "source": "test cache"},
        "summary": {
            "results": 5,
            "symbols": 1,
            "kill": 1,
            "insufficient": 4,
            "iterate": 0,
            "promote": 0,
            "decision_counts": {"kill_or_data_requirement": 1},
        },
        "decisions": [
            {
                "decision": "kill_or_data_requirement",
                "metrics": {
                    "symbol": "AGLD",
                    "total_realized_bps": -1863.1,
                    "sharpe_like": -12.46,
                    "n_windows": 85,
                },
                "judgment": {"verdict": "kill"},
                "params": {"min_net_bps": -1000.0, "horizon_hours": 24.0},
                "killed_scope": "tested thresholds only, not the symbol forever",
                "next_action": "collect_more_data_or_retune_before_kill",
                "promotion_constraints": ["candidate research edge only; not live trading authorization"],
            }
        ],
    }
    (funding / "promotion_packet.json").write_text(json.dumps(packet))
    return funding


def _real_executor(db, tmp_path, client=None):
    return KindRoutingExecutor(
        DelegationTaskRunExecutor(db, client or ContractFakeClient()),
        BacktestTaskRunExecutor(_packet_fixture(tmp_path)),
    )


def test_delegated_research_produces_accepted_deliverable(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-real", workspace_root=tmp_path / "ws")
    client = ContractFakeClient()
    executor = _real_executor(db, tmp_path, client)

    result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "advanced", result.message
    assert campaign.cursor == 1
    task = client.tasks[0]
    assert task.kind == "research_topic"
    assert "WebSearch" in task.allowed_tools
    meta_path = next(Path(campaign.workspace_root, "S1").glob("*/S1_btc_principles.meta.json"))
    meta = json.loads(meta_path.read_text())
    assert meta["generated_by"] == "delegation:research_topic"
    assert meta["sources"] == ["https://bitcoin.org/bitcoin.pdf"]
    event_types = {e["type"] for e in list_events(path=db)}
    assert EventType.DELEGATION_COMPLETED.value in event_types
    assert EventType.POLICY_GATE_PASSED.value in event_types


def test_later_stages_receive_prior_artifact_paths(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-chain", workspace_root=tmp_path / "ws")
    client = ContractFakeClient()
    executor = _real_executor(db, tmp_path, client)

    first = campaign_tick(db, campaign, worker="claude", executor=executor)
    second = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert first.status == "advanced" and second.status == "advanced"
    s1_instruction = client.tasks[0].instruction
    s2_instruction = client.tasks[1].instruction
    assert "第一个阶段" in s1_instruction                       # S1 sees no prior work
    assert campaign.stages[0].artifact_path in s2_instruction   # S2 is handed S1's artifact
    assert first.budget_after is not None                       # delegation spends the will's currency


def test_secret_leaking_worker_fails_the_task(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-leak", workspace_root=tmp_path / "ws")
    executor = _real_executor(db, tmp_path, ContractFakeClient(leak_secret=True))

    result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "task_failed"
    assert campaign.cursor == 0
    assert not list(Path(campaign.workspace_root).glob("S1/*/S1_btc_principles.md"))
    assert EventType.DELEGATION_FAILED.value in {e["type"] for e in list_events(path=db)}


def test_noncompliant_worker_output_is_rejected_by_the_gate(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-bad", workspace_root=tmp_path / "ws")
    sloppy = FakeDelegationClient(ok=True, output_text="# 报告\n\n只有正文，没有必需小节。")
    executor = KindRoutingExecutor(
        DelegationTaskRunExecutor(db, sloppy),
        BacktestTaskRunExecutor(_packet_fixture(tmp_path)),
    )

    result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "deliverable_rejected"
    assert "missing required section" in result.message
    assert campaign.cursor == 0


def test_backtest_stage_renders_packet_numbers_deterministically(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-s4", workspace_root=tmp_path / "ws")
    executor = _real_executor(db, tmp_path)

    for _ in range(4):
        result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "completed", result.message
    assert campaign.status == CampaignStatus.COMPLETED
    artifact = next(Path(campaign.workspace_root, "S4").glob("*/S4_btc_strategy_packet.md"))
    text = artifact.read_text()
    assert "-1863.1" in text            # the number comes from the packet, not a model
    assert "packet_id: testpacket" in text
    assert "## verdicts" in text
    meta = json.loads(next(Path(campaign.workspace_root, "S4").glob("*/S4_btc_strategy_packet.meta.json")).read_text())
    assert meta["generated_by"] == "fundarb-pipeline"


def test_backtest_stage_without_packet_fails_with_guidance(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-nopacket", workspace_root=tmp_path / "ws")
    campaign.cursor = 3  # jump to S4
    executor = KindRoutingExecutor(
        DelegationTaskRunExecutor(db, ContractFakeClient()),
        BacktestTaskRunExecutor(tmp_path / "missing-funding"),
    )

    result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "task_failed"
    assert "will funding" in result.message


def test_resolve_executor_maps_workers(tmp_path):
    assert isinstance(resolve_executor("fake"), FakeTaskRunExecutor)
    assert resolve_executor("claude") is None                       # real worker needs a db for governance events
    real = resolve_executor("claude", db_path=tmp_path / "db.sqlite")
    assert isinstance(real, KindRoutingExecutor)
    assert resolve_executor("unknown", db_path=tmp_path / "db.sqlite") is None


def test_capability_gate_denies_tools_for_backtest_kind(tmp_path):
    from yizhi.campaigns.engine import _task_capabilities

    research_policy, research_tools = _task_capabilities(TaskRunKind.RESEARCH_TOPIC)
    assert research_policy.allow_network_read
    assert "WebSearch" in research_tools

    analysis_policy, analysis_tools = _task_capabilities(TaskRunKind.RUN_ANALYSIS)
    assert not analysis_policy.allow_network_read
    assert analysis_tools == ["Read", "Grep", "Glob"]

    backtest_policy, backtest_tools = _task_capabilities(TaskRunKind.BACKTEST)
    assert not backtest_policy.allow_network_read
    assert backtest_tools == []
