"""Task-run executors: how a campaign task run actually produces its artifact.

W1 hardwired a deterministic fake worker into the tick engine. W2 turns "who
does the work" into an injected TaskRunExecutor so the same governed tick
(budget -> task run -> artifact -> validator -> acceptance gate) can drive a
fake worker (offline CI), a delegated read-only CLI harness (real research),
or an in-process deterministic backtest, without the state machine caring.

The executor contract keeps writes on this side of the trust boundary: a real
worker only *returns text*; the executor materializes artifact + meta inside
the campaign workspace. R0 read-only delegation stays intact. For BACKTEST
stages no LLM touches the numbers — every figure is rendered from the
deterministic fundarb promotion packet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from yizhi.campaigns.schemas import Campaign, CampaignStage, TaskRun, TaskRunKind
from yizhi.campaigns.validators import parse_markdown_sections, parse_markdown_sources
from yizhi.core.schemas import DelegationKind, DelegationTask, ExistenceBudget
from yizhi.engine.delegation import (
    DelegationClient,
    build_delegation_proposal,
    execute_delegation,
)


@dataclass
class TaskRunOutcome:
    ok: bool
    artifact_path: str = ""
    meta_path: str = ""
    summary: str = ""
    trace_ref: str | None = None
    error: str | None = None
    # ExistenceBudget after the run, for executors that spend the will's money
    # (delegation). None for free executors (fake, in-process backtest). The
    # caller is responsible for writing it back — money flows explicitly.
    budget_after: ExistenceBudget | None = None


@runtime_checkable
class TaskRunExecutor(Protocol):
    def execute(self, campaign: Campaign, stage: CampaignStage, task: TaskRun) -> TaskRunOutcome: ...


def task_workspace(campaign: Campaign, stage_id: str, task_id: str) -> Path:
    return Path(campaign.workspace_root) / stage_id / task_id


def artifact_paths(campaign: Campaign, stage: CampaignStage, task: TaskRun) -> tuple[Path, Path]:
    stage_dir = task_workspace(campaign, stage.id, task.id)
    artifact_path = stage_dir / stage.artifact_spec.filename
    meta_path = stage_dir / (stage.artifact_spec.meta_filename or f"{artifact_path.name}.meta.json")
    return artifact_path, meta_path


def write_artifact(
    campaign: Campaign,
    stage: CampaignStage,
    task: TaskRun,
    *,
    text: str,
    generated_by: str,
) -> tuple[str, str]:
    """Materialize artifact + meta inside the campaign workspace.

    Meta reports what the artifact body actually contains (sections and
    sources are parsed out of the text, never taken from a worker's
    self-report), so the acceptance gate validates reality."""
    artifact_path, meta_path = artifact_paths(campaign, stage, task)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(text.strip() + "\n")
    meta = {
        "schema": stage.artifact_spec.schema_name,
        "title": stage.title,
        "sections": parse_markdown_sections(text),
        "sources": parse_markdown_sources(text),
        "generated_by": generated_by,
        "stage_id": stage.id,
        "task_run_id": task.id,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return str(artifact_path), str(meta_path)


class FakeTaskRunExecutor:
    """Deterministic W1 worker: writes a fixed artifact that names itself fake.

    It passes through the same acceptance gate as real workers, so it emits
    real section headings and a placeholder source — form is honest, content
    declares itself fake."""

    def execute(self, campaign: Campaign, stage: CampaignStage, task: TaskRun) -> TaskRunOutcome:
        lines = [
            f"# {stage.title}",
            "",
            f"campaign: {campaign.id}",
            f"stage: {stage.id}",
            f"objective: {stage.objective}",
            "",
            "This is a deterministic W1 fake artifact. It proves the campaign harness, not real BTC research.",
            "",
        ]
        for section in stage.artifact_spec.required_sections:
            lines.append(f"## {section}")
            lines.append("")
            if section == "sources":
                lines.append("- fake://deterministic-w1-placeholder")
            else:
                lines.append("deterministic W1 placeholder")
            lines.append("")
        if stage.revision_notes:
            lines.append("revision_notes:")
            lines.extend(f"- {n}" for n in stage.revision_notes)
        artifact_path, meta_path = write_artifact(
            campaign,
            stage,
            task,
            text="\n".join(lines),
            generated_by="fake",
        )
        return TaskRunOutcome(
            ok=True,
            artifact_path=artifact_path,
            meta_path=meta_path,
            summary="fake worker produced deterministic W1 artifact",
            trace_ref=f"fake:{task.id}",
        )


_TASKRUN_TO_DELEGATION_KIND = {
    TaskRunKind.RESEARCH_TOPIC: DelegationKind.RESEARCH_TOPIC,
    TaskRunKind.RUN_ANALYSIS: DelegationKind.RUN_ANALYSIS,
}


def build_research_instruction(campaign: Campaign, stage: CampaignStage, task: TaskRun) -> str:
    """Compile the stage's artifact contract into the worker brief.

    The worker only returns Markdown text; the executor writes the file. The
    contract pins the exact section slugs so the deterministic gate can check
    the body instead of trusting the worker. Accepted artifacts from earlier
    stages are handed over by path so knowledge flows within the campaign —
    the worker has read tools and may study them."""
    sections = "\n".join(f"## {s}" for s in stage.artifact_spec.required_sections)
    notes = "\n".join(f"- {n}" for n in stage.revision_notes) if stage.revision_notes else "- 无"
    prior = [
        f"- {s.id} {s.title}: {s.artifact_path}"
        for s in campaign.stages
        if s.index < stage.index and s.artifact_path
    ]
    prior_block = (
        "前序阶段已验收的研究产物(建议先用 Read 工具阅读，在其结论上继续，不要重复调研):\n"
        + "\n".join(prior)
        if prior
        else "前序阶段产物: 无(这是第一个阶段)。"
    )
    return (
        f"你是 BTC 研究战役 {campaign.id} 的受限只读研究工人。\n"
        f"阶段 {stage.id}: {stage.title}\n"
        f"阶段目标: {stage.objective}\n"
        f"战役愿景: {campaign.vision}\n"
        f"修订要求:\n{notes}\n"
        f"{prior_block}\n\n"
        "只输出一份 Markdown 研究报告正文，不要输出任何其它内容(不要前言、不要代码块包裹)。硬性要求:\n"
        f"1. 一级标题: # {stage.title}\n"
        f"2. 必须包含以下二级标题，逐字使用这些小写 slug:\n{sections}\n"
        "3. `## sources` 小节用 `- ` 列表逐条列出真实可核查的来源；不得编造 URL。\n"
        "4. 不得给出未经真实计算的收益率/回测数字；无法核实的问题写入 open_questions 或 risks。\n"
        "5. 不得输出任何密钥、凭证或私有信息。"
    )


def strip_code_fence(text: str) -> str:
    """Unwrap a whole-document ``` fence a worker may add despite the contract."""
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped


class DelegationTaskRunExecutor:
    """S1-S3: run research/analysis through the governed R0 delegation path.

    The full governance chain applies per task run: policy gate (read-only
    kinds, no write tools, in-repo cwd) -> existence budget -> harness run ->
    verification (secret scan) -> DELEGATION_* events. The harness returns
    text; this executor materializes it inside the campaign workspace."""

    def __init__(
        self,
        db_path: str | Path,
        client: DelegationClient,
        *,
        budget: ExistenceBudget | None = None,
        delegation_cwd: str = "data",
    ) -> None:
        self.db_path = db_path
        self.client = client
        self.budget = budget or ExistenceBudget()
        self.delegation_cwd = delegation_cwd

    def execute(self, campaign: Campaign, stage: CampaignStage, task: TaskRun) -> TaskRunOutcome:
        kind = _TASKRUN_TO_DELEGATION_KIND.get(task.kind)
        if kind is None:
            return TaskRunOutcome(ok=False, error=f"task kind '{task.kind}' has no delegation mapping")
        delegation = DelegationTask(
            kind=kind,
            instruction=build_research_instruction(campaign, stage, task),
            cwd=self.delegation_cwd,
            allowed_tools=list(task.allowed_tools),
            cost=task.budget.cost,
        )
        proposal = build_delegation_proposal(delegation)
        outcome = execute_delegation(
            proposal, self.client, self.budget, self.db_path, correlation_id=campaign.id
        )
        self.budget = outcome.budget
        if outcome.report is None or outcome.verification is None or not outcome.verification.passed:
            error = (
                (outcome.report.error if outcome.report else None)
                or (outcome.record.error if outcome.record else None)
                or "delegation failed"
            )
            return TaskRunOutcome(
                ok=False,
                error=error,
                trace_ref=outcome.report.id if outcome.report else None,
                budget_after=self.budget,
            )
        text = strip_code_fence(outcome.report.output_text or outcome.report.summary)
        if not text.strip():
            return TaskRunOutcome(
                ok=False,
                error="delegated worker returned empty output",
                trace_ref=outcome.report.id,
                budget_after=self.budget,
            )
        artifact_path, meta_path = write_artifact(
            campaign,
            stage,
            task,
            text=text,
            generated_by=f"delegation:{kind}",
        )
        return TaskRunOutcome(
            ok=True,
            artifact_path=artifact_path,
            meta_path=meta_path,
            summary=f"delegated {kind} produced {stage.artifact_spec.filename}",
            trace_ref=outcome.report.id,
            budget_after=self.budget,
        )


class BacktestTaskRunExecutor:
    """S4: render the strategy packet from the deterministic fundarb pipeline.

    No LLM touches the numbers. Every figure comes from the promotion packet
    that `will funding run-queue` + `will funding packet` produced; this
    executor only reshapes it into the stage's artifact contract."""

    def __init__(self, funding_dir: str | Path = "data/funding") -> None:
        self.funding_dir = Path(funding_dir)

    def execute(self, campaign: Campaign, stage: CampaignStage, task: TaskRun) -> TaskRunOutcome:
        packet_path = self.funding_dir / "promotion_packet.json"
        if not packet_path.exists():
            return TaskRunOutcome(
                ok=False,
                error=f"promotion packet not found: {packet_path}; run `will funding run-queue` and `will funding packet` first",
            )
        try:
            packet = json.loads(packet_path.read_text())
        except ValueError as exc:
            return TaskRunOutcome(ok=False, error=f"promotion packet is not valid JSON: {exc}")
        text = render_strategy_packet_markdown(stage, packet, packet_path)
        artifact_path, meta_path = write_artifact(
            campaign,
            stage,
            task,
            text=text,
            generated_by="fundarb-pipeline",
        )
        return TaskRunOutcome(
            ok=True,
            artifact_path=artifact_path,
            meta_path=meta_path,
            summary=f"rendered strategy packet from {packet_path.name}",
            trace_ref=f"packet:{packet.get('packet_id', 'unknown')}",
        )


def render_strategy_packet_markdown(stage: CampaignStage, packet: dict, packet_path: Path) -> str:
    summary = packet.get("summary", {})
    decisions = packet.get("decisions", [])
    safety = packet.get("safety", {})

    params_seen: set[tuple] = set()
    for decision in decisions:
        params = decision.get("params", {})
        params_seen.add(tuple(sorted(params.items())))

    lines = [
        f"# {stage.title}",
        "",
        f"packet_id: {packet.get('packet_id', 'unknown')}",
        f"rule_version: {packet.get('rule_version', 'unknown')}",
        f"generated_at: {packet.get('generated_at', 'unknown')}",
        "",
        "## strategies",
        "",
        "策略族: funding_diff(双所资金费率差)，enter-all 基线与阈值过滤变体。",
        f"实验参数组合({len(params_seen)} 组，来自确定性实验队列):",
        "",
    ]
    for params in sorted(params_seen):
        rendered = ", ".join(f"{key}={value}" for key, value in params)
        lines.append(f"- {rendered}")

    lines += [
        "",
        "## backtests",
        "",
        f"- 实验总数: {summary.get('results', 0)}",
        f"- 覆盖 symbols: {summary.get('symbols', 0)}",
        f"- KILL: {summary.get('kill', 0)}",
        f"- INSUFFICIENT: {summary.get('insufficient', 0)}",
        f"- ITERATE: {summary.get('iterate', 0)}",
        f"- PROMOTE: {summary.get('promote', 0)}",
        "",
        "| symbol | decision | verdict | total_realized_bps | sharpe_like | n_windows |",
        "|---|---|---|---|---|---|",
    ]
    for decision in decisions:
        metrics = decision.get("metrics", {})
        judgment = decision.get("judgment", {})
        lines.append(
            "| {symbol} | {decision} | {verdict} | {bps} | {sharpe} | {windows} |".format(
                symbol=metrics.get("symbol", "?"),
                decision=decision.get("decision", "?"),
                verdict=judgment.get("verdict", "?"),
                bps=metrics.get("total_realized_bps", "?"),
                sharpe=metrics.get("sharpe_like", "?"),
                windows=metrics.get("n_windows", "?"),
            )
        )

    decision_counts = summary.get("decision_counts", {})
    lines += ["", "## verdicts", ""]
    for name, count in sorted(decision_counts.items()):
        lines.append(f"- {name}: {count}")
    scopes = {d.get("killed_scope") for d in decisions if d.get("killed_scope")}
    for scope in sorted(scopes):
        lines.append(f"- killed_scope: {scope}")

    constraints: list[str] = []
    for decision in decisions:
        for constraint in decision.get("promotion_constraints", []):
            if constraint not in constraints:
                constraints.append(constraint)
    lines += [
        "",
        "## risks",
        "",
        f"- live_trading_authorized: {safety.get('live_trading_authorized', False)}",
        f"- data source: {safety.get('source', 'unknown')}",
        "- INSUFFICIENT 结果为样本量受限，不构成 edge 结论；长尾 edge 论点未证实也未证伪。",
    ]
    lines.extend(f"- {constraint}" for constraint in constraints)

    next_actions: list[str] = []
    for decision in decisions:
        action = decision.get("next_action")
        if action and action not in next_actions:
            next_actions.append(action)
    lines += ["", "## next_actions", ""]
    lines.extend(f"- {action}" for action in next_actions)
    lines += [
        "- 扩展更长历史/多源资金费率回填后重跑队列。",
        "- 引入 walk-forward/out-of-sample 与多重检验协议后再评估晋级。",
        "",
        "## sources",
        "",
        f"- {packet_path}",
        f"- packet_id: {packet.get('packet_id', 'unknown')}",
        f"- source_coverage_id: {packet.get('source_coverage_id', 'unknown')}",
        f"- source_results_path: {packet.get('source_results_path', 'unknown')}",
    ]
    return "\n".join(lines)


class KindRoutingExecutor:
    """Route a task run by kind: BACKTEST goes in-process, the rest delegate."""

    def __init__(self, delegation: DelegationTaskRunExecutor, backtest: BacktestTaskRunExecutor) -> None:
        self.delegation = delegation
        self.backtest = backtest

    def execute(self, campaign: Campaign, stage: CampaignStage, task: TaskRun) -> TaskRunOutcome:
        if task.kind == TaskRunKind.BACKTEST:
            return self.backtest.execute(campaign, stage, task)
        return self.delegation.execute(campaign, stage, task)


def resolve_executor(
    worker: str,
    *,
    db_path: str | Path | None = None,
    delegation_client: DelegationClient | None = None,
    funding_dir: str | Path = "data/funding",
    budget: ExistenceBudget | None = None,
) -> TaskRunExecutor | None:
    """Map a CLI worker name to an executor; None means the tick must deny.

    Real workers ("claude" / "codex") need a db_path for governance events and
    a delegation client; when the client is omitted the manual-gated CLI
    harness config decides whether anything actually runs. `budget` is the
    ExistenceBudget the delegation spends from — the will's single currency;
    omitted means a fresh default wallet (manual CLI-driven mode)."""
    if worker == "fake":
        return FakeTaskRunExecutor()
    if worker in {"claude", "codex"}:
        if db_path is None:
            return None
        if delegation_client is None:
            from yizhi.config import load_delegation_config
            from yizhi.engine.delegation import CliHarnessDelegationClient

            config = load_delegation_config()
            delegation_client = CliHarnessDelegationClient(config)
        return KindRoutingExecutor(
            DelegationTaskRunExecutor(db_path, delegation_client, budget=budget),
            BacktestTaskRunExecutor(funding_dir),
        )
    return None
