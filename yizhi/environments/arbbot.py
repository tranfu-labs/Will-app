"""ArbBot paper/read-only action environment."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from yizhi.actions.runner import run_command
from yizhi.core.schemas import (
    ActionClass,
    ActionProposal,
    ActionRecord,
    ActionStatus,
    EnvironmentName,
    VerificationResult,
    WillState,
    WorldObservation,
)

DEFAULT_ARBBOT_ROOT = Path("/Users/griffith/Projects/AI/ArbBot")

# Sentinel for an in-process probe (no subprocess): run() dispatches it to ArbBot's
# pure backtest functions directly, so the metrics — not just an exit code — become the
# action output. This is the work-surface that turns "exit 0" into real quant evidence.
BACKTEST_SENTINEL = "yizhi:arbbot-backtest"

# REAL funding data, fetched via the Tokyo VPS (the only geo-block-free node) into a local
# cache by scripts/fetch_funding_via_vps.py — see docs/data-via-vps.md. The backtest probe
# reads this cache and runs ArbBot's PURE backtest locally; yizhi's loop never fetches. The
# universe is real instruments (mainstream baseline + long-tail by cross-venue funding diff);
# the agent must discover where a *persistent* edge survives fees — no synthetic data.
DEFAULT_FUNDING_CACHE = Path(__file__).resolve().parents[2] / "data" / "funding_cache.json"


def _parse_kv(args: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in args:
        if "=" in a:
            key, _, value = a.partition("=")
            out[key] = value
    return out


class ArbBotEnvironment:
    name = EnvironmentName.ARBBOT.value

    def __init__(self, root: Path | str = DEFAULT_ARBBOT_ROOT, funding_cache: Path | str = DEFAULT_FUNDING_CACHE) -> None:
        self.root = Path(root)
        self.funding_cache = Path(funding_cache)

    def _load_cache(self) -> dict:
        try:
            return json.loads(self.funding_cache.read_text())
        except (OSError, ValueError):
            return {"symbols": {}}

    def _read_text(self, relative: str, limit: int = 16000) -> str:
        path = self.root / relative
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")[:limit]

    def _git_status(self) -> str:
        completed = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return completed.stdout.strip()

    def observe(self) -> list[WorldObservation]:
        readme = self._read_text("README.md")
        agents = self._read_text("AGENTS.md")
        makefile = self._read_text("Makefile")
        status = self._git_status() if self.root.exists() else "missing ArbBot root"
        readme_lower = readme.lower()
        agents_lower = agents.lower()
        observations = [
            WorldObservation(
                environment=EnvironmentName.ARBBOT,
                source="arbbot.git_status",
                summary="ArbBot worktree status was observed without modification.",
                facts={"status": status, "dirty": "\n M " in f"\n{status}" or "\n?? " in f"\n{status}"},
                salience=0.7,
            ),
            WorldObservation(
                environment=EnvironmentName.ARBBOT,
                source="arbbot.phase_gate",
                summary="ArbBot phase gate was read from README.",
                facts={
                    "phase_4_paper_gate": "phase 4" in readme_lower and "paper" in readme_lower,
                    "phase_5_live_frozen": "phase 5" in readme_lower and "frozen" in readme_lower,
                    "phase_6_cognition_frozen": "phase 6" in readme_lower and "frozen" in readme_lower,
                },
                salience=0.9,
            ),
            WorldObservation(
                environment=EnvironmentName.ARBBOT,
                source="arbbot.safety_boundary",
                summary="ArbBot safety boundary was read from AGENTS/README.",
                facts={
                    "no_real_order": "real order" in readme_lower or "real order" in agents_lower,
                    "no_api_secrets": "api secrets" in readme_lower or "secrets" in agents_lower,
                    "execution_venue_seam": "executionvenue" in readme_lower or "executionvenue" in agents_lower,
                    "llm_not_hot_path": "execution hot path" in readme_lower or "execution hot path" in agents_lower,
                },
                salience=0.9,
            ),
            WorldObservation(
                environment=EnvironmentName.ARBBOT,
                source="arbbot.makefile",
                summary="ArbBot Makefile safe commands were observed.",
                facts={
                    "has_safety": "safety:" in makefile,
                    "has_smoke": "smoke:" in makefile,
                    "has_network": "network:" in makefile,
                    "dry_run_scanners": "--dry-run" in makefile,
                },
                salience=0.6,
            ),
        ]
        return observations

    def propose_actions(self, state: WillState) -> list[ActionProposal]:
        cache = self._load_cache()
        return [
            ActionProposal(
                environment=EnvironmentName.ARBBOT,
                action_class=ActionClass.INTERNAL,
                title="Observe ArbBot git status",
                command=["git", "status", "--short", "--branch"],
                description="Read-only ArbBot worktree status.",
                dry_run=True,
            ),
            ActionProposal(
                environment=EnvironmentName.ARBBOT,
                action_class=ActionClass.INTERNAL,
                title="Run ArbBot safety tests",
                command=["make", "safety"],
                description="Run ArbBot safety-boundary checks only.",
                dry_run=True,
            ),
            ActionProposal(
                environment=EnvironmentName.ARBBOT,
                action_class=ActionClass.INTERNAL,
                title="Run ArbBot offline test suite",
                command=["make", "test"],
                description=(
                    "Run ArbBot's offline tests (excludes integration/network), including the "
                    "backtest and calibration engine — evidence the strategy machinery is sound. "
                    "No network, no orders."
                ),
                dry_run=True,
                experiment=True,
            ),
            ActionProposal(
                environment=EnvironmentName.ARBBOT,
                action_class=ActionClass.FINANCIAL,
                title="Run ArbBot dry-run smoke",
                command=["make", "smoke"],
                description="Run documented dry-run smoke checks without live public network flag.",
                dry_run=True,
                experiment=True,
            ),
            ActionProposal(
                environment=EnvironmentName.ARBBOT,
                action_class=ActionClass.FINANCIAL,
                title="Run funding diff dry-run scanner",
                command=["python", "scripts/smoke_funding_diff_scan.py", "--dry-run"],
                description="Run allowlisted dry-run scanner.",
                dry_run=True,
                experiment=True,
            ),
        ] + [
            ActionProposal(
                environment=EnvironmentName.ARBBOT,
                action_class=ActionClass.FINANCIAL,
                title=f"Backtest funding-diff on {symbol} (enter-all baseline, real data)",
                command=[BACKTEST_SENTINEL, "funding_diff", f"symbol={symbol}", "min_net_bps=-1000", "horizon_hours=24"],
                description=(
                    f"Run ArbBot's pure funding-diff backtest on REAL {symbol} funding history "
                    f"(cross-venue Binance/Bybit via VPS; snapshot diff "
                    f"{cache['symbols'][symbol].get('snapshot_diff', 0) * 100:+.3f}%/period) entering "
                    "ALL windows — the baseline. yizhi AUTHORS the filtered re-tests itself (a "
                    "self-chosen min_net_bps), so a false negative the enter-all baseline dismisses "
                    "can be re-tested at any threshold. Returns real Sharpe/win/PnL/calibration + persistence."
                ),
                dry_run=True,
                experiment=True,
            )
            for symbol in cache.get("symbols", {})
        ]

    def backtest_universe(self) -> list[str]:
        """The tradable instruments yizhi may author a backtest over — the real cached symbols.
        The loop hands this to the hypothesis faculty so the LLM authors parameters (A2.2)
        instead of picking an enumerated threshold; an authored symbol outside it is rejected."""
        return list(self._load_cache().get("symbols", {}))

    def authored_backtest(self, spec: dict) -> ActionProposal:
        """Build the gated proposal for a yizhi-AUTHORED backtest spec. The command is assembled
        HERE from the env's own sentinel/verb (wall 1: authoring can only parameterize a command
        the env already declares, never name a new one); the policy gate then validates the params
        structurally (wall 2). Marked experiment=True so it earns the ledger + replenishment."""
        mnb = float(spec["min_net_bps"])
        horizon = float(spec.get("horizon_hours", 24))
        symbol = str(spec["symbol"])
        return ActionProposal(
            environment=EnvironmentName.ARBBOT,
            action_class=ActionClass.FINANCIAL,
            title=f"Authored backtest: {symbol} @ min_net_bps={mnb:g}",
            command=[BACKTEST_SENTINEL, "funding_diff", f"symbol={symbol}", f"min_net_bps={mnb:g}", f"horizon_hours={horizon:g}"],
            description=(
                f"yizhi-AUTHORED funding-diff backtest on REAL {symbol} data at a self-chosen "
                f"min_net_bps={mnb:g} filter (not an enumerated menu choice)"
                + (f" — {spec['rationale']}" if spec.get("rationale") else "")
            ),
            dry_run=True,
            experiment=True,
        )

    def run(self, proposal: ActionProposal) -> ActionRecord:
        if proposal.command and proposal.command[0] == BACKTEST_SENTINEL:
            return self._run_backtest(proposal)
        return run_command(proposal, cwd=self.root, timeout_seconds=180)

    def _run_backtest(self, proposal: ActionProposal) -> ActionRecord:
        """Probe: run ArbBot's deterministic, in-memory backtest on REAL funding history
        (cached from the Tokyo VPS — see docs/data-via-vps.md; no subprocess, no network).
        Builds the cross-venue earn/hedge series from the cache, reports the metrics PLUS a
        persistence signal (sign-stability) so findings/critique can tell a durable edge from
        snapshot noise. Params come from the command; the policy gate validates the structure."""
        import sys

        params = _parse_kv(list(proposal.command[2:]))
        symbol = params.get("symbol", "")
        entry = self._load_cache().get("symbols", {}).get(symbol)
        if entry is None:
            return ActionRecord(
                proposal_id=proposal.id, environment=proposal.environment,
                status=ActionStatus.FAILED, command=list(proposal.command), exit_code=1,
                stdout="", stderr=f"no cached funding data for {symbol!r}; run scripts/fetch_funding_via_vps.py",
            )
        root = str(self.root)
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            import statistics
            from datetime import datetime, timezone
            from decimal import Decimal

            from arbbot.backtest import backtest_spec  # type: ignore import-not-found
            from arbbot.domain.spec import build_funding_diff_spec  # type: ignore import-not-found
            from arbbot.domain.validation import FundingSample  # type: ignore import-not-found

            bn = {int(k): Decimal(v) for k, v in entry["binance"].items()}
            bb = {int(k): Decimal(v) for k, v in entry["bybit"].items()}
            ts = sorted(set(bn) & set(bb))
            iv = Decimal(str(entry["interval_hours"]))
            # persistence: how often the per-period cross-venue diff keeps the same sign
            diffs = [bn[t] - bb[t] for t in ts]
            mean_diff = statistics.fmean(float(d) for d in diffs)
            sign_stability = sum(1 for d in diffs if (d > 0) == (mean_diff > 0)) / len(diffs)
            # earn = the higher-funding leg (short it, collect funding); hedge = the lower
            hi_is_binance = statistics.fmean(float(bn[t]) for t in ts) >= statistics.fmean(float(bb[t]) for t in ts)

            def make(venue: str, d: dict) -> list:
                return [FundingSample(venue=venue, symbol=f"{symbol}/USDT:USDT", funding_rate=d[t],
                        interval_hours=iv, observed_at=datetime.fromtimestamp(t / 1000, timezone.utc)) for t in ts]

            earn = make("binance", bn) if hi_is_binance else make("bybit", bb)
            hedge = make("bybit", bb) if hi_is_binance else make("binance", bn)
            min_net = Decimal(str(params.get("min_net_bps", "-1000")))
            horizon = Decimal(str(params.get("horizon_hours", "24")))
            spec = build_funding_diff_spec(min_net_bps=min_net, horizon_hours=horizon, max_hold_hours=Decimal("72"))
            res = backtest_spec(spec, earn, hedge, observation_ts=datetime.now(timezone.utc))
            m = res.metrics
            stdout = (
                f"backtest funding_diff symbol={symbol} (REAL Binance/Bybit, n={len(ts)} periods, iv={iv}h, "
                f"min_net_bps={min_net}): n_windows={res.n_windows} n_entered={res.n_entered} "
                f"sharpe_like={float(m.sharpe_like):.2f} win_rate={float(m.win_rate):.2f} "
                f"max_drawdown_bps={float(m.max_drawdown_bps):.1f} total_realized_bps={float(m.total_realized_bps):.1f} "
                f"calibration_verdict={getattr(res.calibration.verdict, 'value', res.calibration.verdict)} "
                f"persistence_sign_stability={sign_stability:.2f}"
            )
            return ActionRecord(
                proposal_id=proposal.id, environment=proposal.environment,
                status=ActionStatus.SUCCEEDED, command=list(proposal.command), exit_code=0,
                stdout=stdout, stderr="",
            )
        except Exception as exc:
            return ActionRecord(
                proposal_id=proposal.id, environment=proposal.environment,
                status=ActionStatus.FAILED, command=list(proposal.command), exit_code=1,
                stdout="", stderr=f"backtest probe error: {type(exc).__name__}: {exc}",
            )

    def verify(self, record: ActionRecord) -> VerificationResult:
        passed = record.status == ActionStatus.SUCCEEDED and record.exit_code == 0
        forbidden_markers = ["--live-public", "place_order", "apiKey", "secret"]
        command_text = " ".join(record.command)
        no_forbidden_marker = not any(marker in command_text for marker in forbidden_markers)
        return VerificationResult(
            action_record_id=record.id,
            passed=passed and no_forbidden_marker,
            checks=["exit_code_is_zero", "no_live_or_secret_marker"],
            summary=(
                "ArbBot paper/read-only action succeeded."
                if passed and no_forbidden_marker
                else "ArbBot paper/read-only action failed or violated marker check."
            ),
        )
