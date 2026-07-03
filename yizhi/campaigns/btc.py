"""BTC research campaign template."""

from __future__ import annotations

from pathlib import Path

from yizhi.campaigns.schemas import (
    AcceptanceGate,
    ArtifactSpec,
    Campaign,
    CampaignBudget,
    CampaignStage,
    TaskRunKind,
)


def _stage(
    *,
    sid: str,
    index: int,
    title: str,
    objective: str,
    kind: TaskRunKind,
    schema_name: str,
    filename: str,
    sections: list[str],
) -> CampaignStage:
    return CampaignStage(
        id=sid,
        index=index,
        title=title,
        objective=objective,
        allowed_task_kinds=[kind],
        artifact_spec=ArtifactSpec(
            schema_name=schema_name,
            filename=filename,
            meta_filename=filename.removesuffix(".md") + ".meta.json",
            required_sections=sections,
        ),
        acceptance_gate=AcceptanceGate(required_schema=schema_name, min_sections=sections),
    )


def build_btc_campaign(
    *,
    campaign_id: str | None = None,
    workspace_root: str | Path | None = None,
) -> Campaign:
    cid = campaign_id or "btc-mvp"
    root = Path(workspace_root or "data/campaigns") / cid
    return Campaign(
        id=cid,
        title="BTC Research Campaign MVP",
        vision="搞清楚 BTC 投资机会，产出经确定性判定的交易策略研究。",
        workspace_root=str(root),
        budget=CampaignBudget(max_stages=4, max_revisions=8, max_task_runs=16, max_worker_cost=40.0),
        stages=[
            _stage(
                sid="S1",
                index=1,
                title="BTC 原理研究",
                objective="研究 BTC 白皮书、共识机制、货币属性、主要风险与开放问题。",
                kind=TaskRunKind.RESEARCH_TOPIC,
                schema_name="btc_principles_report_v1",
                filename="S1_btc_principles.md",
                sections=["summary", "mechanism", "risks", "open_questions", "sources"],
            ),
            _stage(
                sid="S2",
                index=2,
                title="交易场所调研",
                objective="调研 BTC 现货、合约、期货交易场所、费率、流动性、API 与风险。",
                kind=TaskRunKind.RESEARCH_TOPIC,
                schema_name="btc_venues_report_v1",
                filename="S2_btc_venues.md",
                sections=["venues", "spot", "perp", "futures", "fees", "liquidity", "api", "risks"],
            ),
            _stage(
                sid="S3",
                index=3,
                title="品种与走势分析",
                objective="分析 BTC 现货、合约、期货特性与 K 线市场结构。",
                kind=TaskRunKind.RUN_ANALYSIS,
                schema_name="btc_market_structure_report_v1",
                filename="S3_btc_market_structure.md",
                sections=["summary", "instruments", "market_structure", "open_questions"],
            ),
            _stage(
                sid="S4",
                index=4,
                title="策略设计与回测",
                objective="设计候选策略并回测，产出 KILL/ITERATE/PROMOTE 策略 packet。",
                kind=TaskRunKind.BACKTEST,
                schema_name="btc_strategy_packet_v1",
                filename="S4_btc_strategy_packet.md",
                sections=["strategies", "backtests", "verdicts", "risks", "next_actions"],
            ),
        ],
    )
