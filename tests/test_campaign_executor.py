from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from will.campaigns.btc import build_btc_campaign
from will.campaigns.engine import campaign_tick
from will.campaigns.executor import (
    BacktestTaskRunExecutor,
    DelegationTaskRunExecutor,
    FakeTaskRunExecutor,
    KindRoutingExecutor,
    resolve_executor,
)
from will.campaigns.schemas import CampaignStatus, TaskRunKind
from will.core.schemas import DelegationReport, DelegationTask, EventType
from will.workers.delegation import FakeDelegationClient
from will.ledger.store import init_db, list_events


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


def _btc_fixture(tmp_path, *, records: int = 240):
    btc = tmp_path / "btc"
    btc.mkdir()
    start = date(2020, 1, 1)
    payload = {
        "source": "unit-test synthetic BTC daily cache",
        "records": [
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "open": 10000.0 + i * 10,
                "high": 10100.0 + i * 10,
                "low": 9900.0 + i * 10,
                "close": 10000.0 + i * 10,
                "volume": 1.0,
            }
            for i in range(records)
        ],
    }
    (btc / "btc_ohlcv_daily.json").write_text(json.dumps(payload))
    return btc


def _real_executor(db, tmp_path, client=None):
    return KindRoutingExecutor(
        DelegationTaskRunExecutor(db, client or ContractFakeClient()),
        BacktestTaskRunExecutor(_btc_fixture(tmp_path)),
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
    meta_path = next(Path(campaign.workspace_root, "S1").glob("*/S1_btc_problem_plan.meta.json"))
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
    assert not list(Path(campaign.workspace_root).glob("S1/*/S1_btc_problem_plan.md"))
    assert EventType.DELEGATION_FAILED.value in {e["type"] for e in list_events(path=db)}


def test_noncompliant_worker_output_is_rejected_by_the_gate(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-bad", workspace_root=tmp_path / "ws")
    sloppy = FakeDelegationClient(ok=True, output_text="# 报告\n\n只有正文，没有必需小节。")
    executor = KindRoutingExecutor(
        DelegationTaskRunExecutor(db, sloppy),
        BacktestTaskRunExecutor(_btc_fixture(tmp_path)),
    )

    result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "deliverable_rejected"
    assert "missing required section" in result.message
    assert campaign.cursor == 0


def test_backtest_stage_uses_btc_cache_not_fundarb_packet(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-s4", workspace_root=tmp_path / "ws")
    executor = _real_executor(db, tmp_path)

    for _ in range(4):
        result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "advanced", result.message
    assert campaign.status == CampaignStatus.ACTIVE
    assert campaign.cursor == 4
    artifact = next(Path(campaign.workspace_root, "S4").glob("*/S4_btc_explainable_backtest.md"))
    text = artifact.read_text()
    assert "buy_and_hold" in text
    assert "dca_equal_daily" in text
    assert "sma_50_200" in text
    assert "promotion_packet" not in text
    assert "funding_diff" not in text
    assert "## verdicts" in text
    meta = json.loads(next(Path(campaign.workspace_root, "S4").glob("*/S4_btc_explainable_backtest.meta.json")).read_text())
    assert meta["generated_by"] == "btc-backtest-pipeline"
    evidence = json.loads(next(Path(campaign.workspace_root, "S4").glob("*/btc_backtest_results.json")).read_text())
    assert evidence["record_type"] == "btc_baseline_backtest_v1"
    assert evidence["dataset"]["record_count"] == 240

    final = campaign_tick(db, campaign, worker="claude", executor=executor)
    assert final.status == "completed", final.message
    assert campaign.status == CampaignStatus.COMPLETED
    assert next(Path(campaign.workspace_root, "S5").glob("*/S5_btc_research_pack.md"))


def test_backtest_stage_without_btc_cache_fails_with_guidance(tmp_path):
    db = init_db(tmp_path / "state.sqlite")
    campaign = build_btc_campaign(campaign_id="btc-nopacket", workspace_root=tmp_path / "ws")
    campaign.cursor = 3  # jump to S4
    executor = KindRoutingExecutor(
        DelegationTaskRunExecutor(db, ContractFakeClient()),
        BacktestTaskRunExecutor(tmp_path / "missing-btc-cache"),
    )

    result = campaign_tick(db, campaign, worker="claude", executor=executor)

    assert result.status == "task_failed"
    assert "BTC OHLCV cache" in result.message


def test_resolve_executor_maps_workers(tmp_path):
    assert isinstance(resolve_executor("fake"), FakeTaskRunExecutor)
    assert resolve_executor("claude") is None                       # real worker needs a db for governance events
    real = resolve_executor("claude", db_path=tmp_path / "db.sqlite")
    assert isinstance(real, KindRoutingExecutor)
    assert resolve_executor("unknown", db_path=tmp_path / "db.sqlite") is None


def test_capability_gate_denies_tools_for_backtest_kind(tmp_path):
    from will.campaigns.engine import _task_capabilities

    research_policy, research_tools = _task_capabilities(TaskRunKind.RESEARCH_TOPIC)
    assert research_policy.allow_network_read
    assert "WebSearch" in research_tools

    analysis_policy, analysis_tools = _task_capabilities(TaskRunKind.RUN_ANALYSIS)
    assert not analysis_policy.allow_network_read
    assert analysis_tools == ["Read", "Grep", "Glob"]

    backtest_policy, backtest_tools = _task_capabilities(TaskRunKind.BACKTEST)
    assert not backtest_policy.allow_network_read
    assert backtest_tools == []
