"""Task-run executors: how a campaign task run actually produces its artifact.

W1 hardwired a deterministic fake worker into the tick engine. W2 turns "who
does the work" into an injected TaskRunExecutor so the same governed tick
(budget -> task run -> artifact -> validator -> acceptance gate) can drive a
fake worker (offline CI), a delegated read-only CLI harness (real research),
or an in-process deterministic backtest, without the state machine caring.

The executor contract keeps writes on this side of the trust boundary: a real
worker only *returns text*; the executor materializes artifact + meta inside
the campaign workspace. R0 read-only delegation stays intact. For BACKTEST
stages no LLM touches the numbers: the BTC MVP path reads an auditable local
BTC OHLCV cache and computes explainable baselines deterministically.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from will.campaigns.schemas import Campaign, CampaignStage, TaskRun, TaskRunKind
from will.campaigns.validators import parse_markdown_sections, parse_markdown_sources
from will.core.schemas import DelegationKind, DelegationTask, ExistenceBudget
from will.workers.delegation import (
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
    TaskRunKind.DRAFT_ARTIFACT: DelegationKind.RUN_ANALYSIS,
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
    """Research/analysis/drafting stages through the governed R0 delegation path.

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


class BtcBacktestTaskRunExecutor:
    """S4 for the BTC MVP: deterministic baseline backtests over BTC daily data.

    This executor does not fetch network data and does not ask an LLM for
    numbers. It reads an auditable local cache, writes a JSON evidence file next
    to the Markdown artifact, and renders the required campaign sections."""

    def __init__(self, data_dir: str | Path = "data/btc") -> None:
        self.data_dir = Path(data_dir)

    def execute(self, campaign: Campaign, stage: CampaignStage, task: TaskRun) -> TaskRunOutcome:
        data_path = self.data_dir / "btc_ohlcv_daily.json"
        if not data_path.exists():
            return TaskRunOutcome(
                ok=False,
                error=(
                    f"BTC OHLCV cache not found: {data_path}; create an auditable read-only BTC "
                    "daily cache before S4, or revisit S3 data acquisition."
                ),
            )
        try:
            dataset = json.loads(data_path.read_text())
        except ValueError as exc:
            return TaskRunOutcome(ok=False, error=f"BTC OHLCV cache is not valid JSON: {exc}")
        try:
            records, source = load_btc_ohlcv_records(dataset)
        except ValueError as exc:
            return TaskRunOutcome(ok=False, error=f"BTC OHLCV cache rejected: {exc}")

        result = compute_btc_baseline_backtests(records, source=source, data_path=data_path)
        artifact_path, _ = artifact_paths(campaign, stage, task)
        evidence_path = artifact_path.parent / "btc_backtest_results.json"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        text = render_btc_backtest_markdown(stage, result, data_path, evidence_path)
        artifact_path, meta_path = write_artifact(
            campaign,
            stage,
            task,
            text=text,
            generated_by="btc-backtest-pipeline",
        )
        return TaskRunOutcome(
            ok=True,
            artifact_path=artifact_path,
            meta_path=meta_path,
            summary=f"computed BTC baseline backtests from {data_path.name}",
            trace_ref=f"btc-backtest:{result['dataset']['record_count']}:{result['dataset']['start']}:{result['dataset']['end']}",
        )


def load_btc_ohlcv_records(dataset) -> tuple[list[dict], str]:
    """Accept either a bare record list or an object with records/source."""
    if isinstance(dataset, dict):
        records = dataset.get("records")
        source = str(dataset.get("source") or dataset.get("source_url") or "local BTC OHLCV cache")
    else:
        records = dataset
        source = "local BTC OHLCV cache"
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty list")

    parsed: list[dict] = []
    last_date = ""
    for index, row in enumerate(records):
        if not isinstance(row, dict):
            raise ValueError(f"record {index} must be an object")
        date = str(row.get("date") or row.get("time") or "").strip()
        if not date:
            raise ValueError(f"record {index} is missing date")
        close_raw = row.get("close")
        if close_raw is None:
            raise ValueError(f"record {index} is missing close")
        try:
            close = float(close_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"record {index} close is not numeric") from exc
        if close <= 0:
            raise ValueError(f"record {index} close must be positive")
        if last_date and date <= last_date:
            raise ValueError("records must be sorted by ascending date with no duplicates")
        last_date = date
        parsed.append({"date": date, "close": close})
    if len(parsed) < 2:
        raise ValueError("at least two daily records are required")
    return parsed, source


def _pct(value: float) -> float:
    return round(value * 100.0, 4)


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = (value / peak) - 1.0
        worst = min(worst, drawdown)
    return worst


def _annualized_volatility(closes: list[float]) -> float:
    returns = [(closes[i] / closes[i - 1]) - 1.0 for i in range(1, len(closes))]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((ret - mean) ** 2 for ret in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(365.0)


def _cagr(start_value: float, end_value: float, days: int) -> float | None:
    if days <= 0 or start_value <= 0 or end_value <= 0:
        return None
    years = days / 365.0
    if years <= 0:
        return None
    return (end_value / start_value) ** (1.0 / years) - 1.0


def compute_btc_baseline_backtests(records: list[dict], *, source: str, data_path: Path) -> dict:
    closes = [float(row["close"]) for row in records]
    dates = [str(row["date"]) for row in records]
    days = max(1, len(records) - 1)
    start_close = closes[0]
    end_close = closes[-1]

    buy_hold_equity = [close / start_close for close in closes]
    buy_hold_return = (end_close / start_close) - 1.0

    # DCA: invest one equal cash unit per record, then mark all accumulated BTC
    # at the final close. It is intentionally simple and explainable.
    btc_units = sum(1.0 / close for close in closes)
    dca_contributed = float(len(closes))
    dca_end_value = btc_units * end_close
    dca_return = (dca_end_value / dca_contributed) - 1.0

    sma_metrics: dict[str, float | int | str | None] = {
        "short_window_days": 50,
        "long_window_days": 200,
        "total_return_pct": None,
        "max_drawdown_pct": None,
        "trades": 0,
        "verdict": "INSUFFICIENT",
    }
    if len(closes) >= 220:
        cash = 1.0
        btc = 0.0
        trades = 0
        equity = []
        for i, close in enumerate(closes):
            short = sum(closes[max(0, i - 49): i + 1]) / min(i + 1, 50)
            long = sum(closes[max(0, i - 199): i + 1]) / min(i + 1, 200)
            invested = btc > 0.0
            if i >= 199 and short > long and not invested:
                btc = cash / close
                cash = 0.0
                trades += 1
            elif i >= 199 and short <= long and invested:
                cash = btc * close
                btc = 0.0
                trades += 1
            equity.append(cash + btc * close)
        sma_return = equity[-1] - 1.0
        sma_metrics = {
            "short_window_days": 50,
            "long_window_days": 200,
            "total_return_pct": _pct(sma_return),
            "max_drawdown_pct": _pct(_max_drawdown(equity)),
            "trades": trades,
            "verdict": "BASELINE_RESULT",
        }

    buy_hold_cagr = _cagr(start_close, end_close, days)
    return {
        "record_type": "btc_baseline_backtest_v1",
        "dataset": {
            "source": source,
            "path": str(data_path),
            "record_count": len(records),
            "start": dates[0],
            "end": dates[-1],
            "start_close": start_close,
            "end_close": end_close,
        },
        "strategies": {
            "buy_and_hold": {
                "total_return_pct": _pct(buy_hold_return),
                "cagr_pct": None if buy_hold_cagr is None else _pct(buy_hold_cagr),
                "max_drawdown_pct": _pct(_max_drawdown(buy_hold_equity)),
                "volatility_annual_pct": _pct(_annualized_volatility(closes)),
                "verdict": "BASELINE_RESULT",
            },
            "dca_equal_daily": {
                "contributions": len(closes),
                "total_return_pct": _pct(dca_return),
                "verdict": "BASELINE_RESULT",
            },
            "sma_50_200": sma_metrics,
            "cash": {
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "verdict": "BASELINE_RESULT",
            },
        },
        "verdict": "BASELINE_RESULT",
        "limitations": [
            "research-only historical baseline, not investment advice",
            "daily close data ignores intraday execution, fees, slippage, taxes, custody, and liquidity",
            "DCA baseline assumes equal cash contribution per record",
            "SMA 50/200 requires at least 220 daily records; otherwise marked INSUFFICIENT",
        ],
    }


def render_btc_backtest_markdown(stage: CampaignStage, result: dict, data_path: Path, evidence_path: Path) -> str:
    dataset = result["dataset"]
    strategies = result["strategies"]
    lines = [
        f"# {stage.title}",
        "",
        "## strategies",
        "",
        "- buy_and_hold: first close to last close.",
        "- dca_equal_daily: one equal cash contribution per daily record.",
        "- sma_50_200: long-only 50/200-day moving-average baseline when enough records exist.",
        "- cash: zero-return baseline.",
        "",
        "## backtests",
        "",
        f"- dataset_source: {dataset['source']}",
        f"- record_count: {dataset['record_count']}",
        f"- period: {dataset['start']} to {dataset['end']}",
        f"- start_close: {dataset['start_close']}",
        f"- end_close: {dataset['end_close']}",
        "",
        "## metrics",
        "",
        "| strategy | total_return_pct | cagr_pct | max_drawdown_pct | volatility_annual_pct | verdict |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, metrics in strategies.items():
        lines.append(
            "| {name} | {ret} | {cagr} | {dd} | {vol} | {verdict} |".format(
                name=name,
                ret=metrics.get("total_return_pct", "n/a"),
                cagr=metrics.get("cagr_pct", "n/a"),
                dd=metrics.get("max_drawdown_pct", "n/a"),
                vol=metrics.get("volatility_annual_pct", "n/a"),
                verdict=metrics.get("verdict", "n/a"),
            )
        )
    lines += [
        "",
        "## verdicts",
        "",
        f"- campaign_verdict: {result['verdict']}",
        f"- sma_50_200: {strategies['sma_50_200']['verdict']}",
        "- No strategy is promoted for live or paper trading by this artifact.",
        "",
        "## risks",
        "",
    ]
    lines.extend(f"- {item}" for item in result["limitations"])
    lines += [
        "",
        "## next_actions",
        "",
        "- If record_count is below the intended eight-year coverage, revisit S3 and extend the auditable cache.",
        "- Add fees, slippage, tax assumptions, and out-of-sample checks before treating any result as decision support.",
        "- Ask Soul lens review only after deterministic numbers and data-quality evidence exist.",
        "",
        "## sources",
        "",
        f"- {data_path}",
        f"- {evidence_path}",
        f"- dataset_source: {dataset['source']}",
    ]
    return "\n".join(lines)


class KindRoutingExecutor:
    """Route a task run by kind: BACKTEST goes in-process, the rest delegate."""

    def __init__(self, delegation: DelegationTaskRunExecutor, backtest: TaskRunExecutor) -> None:
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
    btc_data_dir: str | Path = "data/btc",
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
            from will.config import load_delegation_config
            from will.workers.delegation import CliHarnessDelegationClient

            config = load_delegation_config()
            delegation_client = CliHarnessDelegationClient(config)
        return KindRoutingExecutor(
            DelegationTaskRunExecutor(db_path, delegation_client, budget=budget),
            BtcBacktestTaskRunExecutor(btc_data_dir),
        )
    return None

BacktestTaskRunExecutor = BtcBacktestTaskRunExecutor
