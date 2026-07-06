"""BTC research campaign template."""

from __future__ import annotations

from pathlib import Path

from will.campaigns.schemas import (
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
        acceptance_gate=AcceptanceGate(
            required_schema=schema_name,
            min_sections=sections,
            require_sources=True,
        ),
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
        vision=(
            "从用户模糊问题出发，让 Will 自主完成 BTC 基础研究、交易方式研究、"
            "数据获取决策、最小可解释回测与最终研究包交付。"
        ),
        workspace_root=str(root),
        budget=CampaignBudget(max_stages=5, max_revisions=8, max_task_runs=20, max_worker_cost=50.0),
        stages=[
            _stage(
                sid="S1",
                index=1,
                title="问题理解与研究计划",
                objective=(
                    "理解用户关于 BTC 是什么、如何交易、如何盈利的模糊问题，"
                    "拆成可执行研究目标、阶段计划、证据需求与安全边界。"
                ),
                kind=TaskRunKind.RESEARCH_TOPIC,
                schema_name="btc_problem_plan_v1",
                filename="S1_btc_problem_plan.md",
                sections=["user_question", "research_goals", "plan", "evidence_needs", "safety_bounds", "sources"],
            ),
            _stage(
                sid="S2",
                index=2,
                title="BTC 机制与交易方式研究",
                objective="研究 BTC 基础机制、供给/共识、波动来源、现货/合约/ETF 等交易方式、成本与风险。",
                kind=TaskRunKind.RESEARCH_TOPIC,
                schema_name="btc_basics_trading_report_v1",
                filename="S2_btc_basics_trading.md",
                sections=["summary", "mechanism", "trading_methods", "profit_sources", "costs", "risks", "sources"],
            ),
            _stage(
                sid="S3",
                index=3,
                title="数据获取决策与缓存",
                objective=(
                    "评估公开只读数据、本地缓存、第三方数据/API key 等候选，"
                    "默认只使用安全权限，取得或生成可审计 BTC 历史数据缓存。"
                ),
                kind=TaskRunKind.RUN_ANALYSIS,
                schema_name="btc_data_acquisition_decision_v1",
                filename="S3_btc_data_acquisition.md",
                sections=[
                    "candidate_sources",
                    "decision",
                    "permission_boundary",
                    "cache_artifact",
                    "data_quality",
                    "open_questions",
                    "sources",
                ],
            ),
            _stage(
                sid="S4",
                index=4,
                title="最小可解释回测",
                objective=(
                    "由 Will 选择并执行最小可解释 BTC 回测 baseline，例如 buy-and-hold、DCA、"
                    "简单均线和现金基准；不足时给出 INSUFFICIENT 与返工建议。"
                ),
                kind=TaskRunKind.BACKTEST,
                schema_name="btc_explainable_backtest_v1",
                filename="S4_btc_explainable_backtest.md",
                sections=["strategies", "backtests", "metrics", "verdicts", "risks", "next_actions", "sources"],
            ),
            _stage(
                sid="S5",
                index=5,
                title="最终答案与研究包",
                objective=(
                    "综合阶段产物、数据证据和回测证据，生成用户可读的 BTC 完整研究包："
                    "是什么、如何交易、如何盈利、历史证据、风险限制与下一步。"
                ),
                kind=TaskRunKind.DRAFT_ARTIFACT,
                schema_name="btc_research_pack_v1",
                filename="S5_btc_research_pack.md",
                sections=[
                    "final_answer",
                    "stage_evidence",
                    "data_and_backtest_evidence",
                    "risks_and_limits",
                    "next_steps",
                    "sources",
                ],
            ),
        ],
    )
