"""Command line interface for Will Agent v0."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from typing import Any

from yizhi.campaigns.btc import build_btc_campaign
from yizhi.campaigns.engine import campaign_tick, revisit_stage
from yizhi.campaigns.store import load_campaign, save_campaign_started
from yizhi.channels.notify import event_to_message, make_channel
from yizhi.config import load_channel_config, load_delegation_config
from yizhi.core.ids import new_id
from yizhi.core.schemas import DelegationKind, DelegationTask, EventType, WillState
from yizhi.engine.delegation import CliHarnessDelegationClient, build_delegation_proposal, execute_delegation
from yizhi.engine.loop import environment_from_name, run_step
from yizhi.engine.runner import run_until
from yizhi.eval.loops import list_loop_evals
from yizhi.fundarb.dataset import build_coverage_report, ingest_cache, write_coverage_report
from yizhi.fundarb.execution import execute_experiment_queue
from yizhi.fundarb.experiments import build_and_write_queue
from yizhi.fundarb.packets import build_and_write_packet
from yizhi.state.snapshots import load_or_create_state
from yizhi.state.store import DEFAULT_DB_PATH, append_event, init_db, list_events, load_latest_snapshot


def _print_kv(data: dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")


def cmd_init(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    state = load_or_create_state(db_path)
    _print_kv({"db": str(db_path), "state_id": state.id, "identity": state.identity.name})
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    env = environment_from_name(args.env, args.root)
    correlation_id = new_id("observe")
    event_ids: list[str] = []
    for obs in env.observe():
        event_ids.append(
            append_event(
                EventType.OBSERVATION_RECORDED,
                aggregate_type="observation",
                aggregate_id=obs.id,
                payload=obs,
                correlation_id=correlation_id,
                path=db_path,
            )
        )
    _print_kv(
        {
            "event ids": event_ids,
            "proposal id": "not_run",
            "policy decision": "not_run",
            "action status": "not_run",
            "verification status": "not_run",
            "loop status": "partial",
        }
    )
    return 0


def cmd_step(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    state = load_or_create_state(db_path)
    env = environment_from_name(
        args.env,
        args.root,
        db_path=db_path,
        campaign_id=getattr(args, "campaign_id", None),
        worker=getattr(args, "worker", "fake"),
        state=state,
    )
    result = run_step(env, state, db_path)
    _print_kv(
        {
            "event ids": result.event_ids,
            "proposal id": result.proposal_id,
            "policy decision": result.policy_decision,
            "action status": result.action_status,
            "verification status": result.verification_status,
            "loop status": result.loop_status,
        }
    )
    return 0


def _make_vps_fetch_hook(escalate: bool = True) -> "Any":
    """A6 frontier-widening hook for `will run --fetch-on-exhaust`. On exhaustion the
    runner calls this OFF-LOOP (run_step never SSHes): it invokes the VPS fetch script,
    escalating depth/breadth each call, and returns True iff the funding cache actually
    changed — so a barren fetch reports no new data and the run halts cleanly. Opt-in;
    needs VPS access. The fetch is plumbing the offline suite cannot exercise; the runner
    mechanism it feeds is covered with a fake hook in tests/test_runner.py."""
    import hashlib
    import os
    import subprocess
    import sys
    from pathlib import Path

    from yizhi.environments.arbbot import DEFAULT_FUNDING_CACHE

    cache = Path(DEFAULT_FUNDING_CACHE)
    script = str(Path(__file__).resolve().parents[1] / "scripts" / "fetch_funding_via_vps.py")
    state = {"calls": 0}

    def _digest() -> str:
        try:
            return hashlib.sha256(cache.read_bytes()).hexdigest()
        except OSError:
            return ""

    def hook() -> bool:
        state["calls"] += 1
        env = dict(os.environ)
        if escalate:  # ask for progressively deeper history + a wider long tail each time
            env["YIZHI_FETCH_HIST_LIMIT"] = str(200 + 300 * state["calls"])
            env["YIZHI_FETCH_N_LONGTAIL"] = str(12 + 12 * state["calls"])
        before = _digest()
        proc = subprocess.run([sys.executable, script], env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"  fetch hook: VPS fetch failed — {proc.stderr.strip()[-200:]}")
            return False
        return _digest() != before

    return hook


def cmd_run(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    state = load_or_create_state(db_path)
    if args.vision:
        state.vision = args.vision
    env = environment_from_name(
        args.env,
        args.root,
        db_path=db_path,
        campaign_id=getattr(args, "campaign_id", None),
        worker=getattr(args, "worker", "fake"),
        state=state,
    )

    def on_step(n: int, result: Any, st: WillState) -> None:
        print(f"step {n:>3}: status={result.loop_status} action={result.proposal_id} budget={st.budget.balance:.1f}")

    fetch_hook = _make_vps_fetch_hook() if getattr(args, "fetch_on_exhaust", False) else None
    channel = None
    if getattr(args, "channel_root", None):
        # Opt-in dialogue seam: drain this inbox each step (words → observations,
        # vision/kill-goal → governed state changes, asks → answers to the outbox).
        channel = make_channel(replace(load_channel_config(), root=args.channel_root))
    outcome = run_until(
        env,
        state,
        db_path,
        max_steps=args.max_steps,
        stop_on_stuck=not args.no_stuck_stop,
        sleep=args.sleep,
        on_step=on_step,
        fetch_hook=fetch_hook,
        channel=channel,
    )
    _print_kv(
        {
            "steps": outcome.steps,
            "stop_reason": outcome.stop_reason,
            "budget": f"{outcome.budget_balance:.1f}",
            "halted": outcome.halted,
            "data_fetches": outcome.fetches,
        }
    )
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    events = list_events(path=db_path)
    for event in events[-args.limit :]:
        print(
            json.dumps(
                {
                    "id": event["id"],
                    "ts": event["ts"],
                    "type": event["type"],
                    "aggregate_type": event["aggregate_type"],
                    "aggregate_id": event["aggregate_id"],
                    "correlation_id": event["correlation_id"],
                    "status": event["status"],
                    "payload": event["payload"],
                },
                ensure_ascii=False,
            )
        )
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    state = load_latest_snapshot(db_path) or WillState()
    print(state.model_dump_json(indent=2))
    return 0


def cmd_delegate(args: argparse.Namespace) -> int:
    """Run one governed read-only delegation through gate → budget → run → verify.

    Manual entry point (R0; docs/resident-operator-plan.md). The harness is OFF unless
    DelegationConfig is enabled, so by default this exercises the full governance closure
    and reports "delegation disabled" instead of starting a subprocess. Budget pressure is
    read from current state but not persisted — a one-shot diagnostic; the semantic events
    are the audit trail."""
    db_path = init_db(args.db)
    state = load_or_create_state(db_path)
    config = load_delegation_config()
    tools = [t.strip() for t in args.allowed_tools.split(",") if t.strip()] or list(config.default_allowed_tools)
    task = DelegationTask(kind=DelegationKind(args.kind), instruction=args.instruction, cwd=args.cwd, allowed_tools=tools)
    outcome = execute_delegation(build_delegation_proposal(task), CliHarnessDelegationClient(config), state.budget, db_path)
    _print_kv(
        {
            "kind": task.kind,
            "harness": config.harness if config.active else "disabled",
            "policy decision": outcome.gate.decision,
            "policy reasons": outcome.gate.reasons or ["(allowed)"],
            "action status": outcome.record.status if outcome.record else "none",
            "verification passed": outcome.verification.passed if outcome.verification else "n/a",
            "budget after": f"{outcome.budget.balance:.1f}",
            "summary": outcome.report.summary if outcome.report else "(not run)",
        }
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Report reportable events to the configured channel and drain inbound commands.

    Manual entry to the R2 interaction layer (docs/resident-operator-plan.md). Defaults to
    the offline file-backed local_inbox; Telegram is opt-in via config. Reporting is
    infrastructure-level — it records nothing on the will budget."""
    db_path = init_db(args.db)
    config = load_channel_config()
    if args.channel_root:
        config = replace(config, root=args.channel_root)
    channel = make_channel(config)
    events = list_events(path=db_path, limit=args.limit, newest_first=True)
    sent = 0
    for event in reversed(events):
        message = event_to_message(event)
        if message is not None:
            channel.send(message)
            sent += 1
    inbound = channel.poll()
    _print_kv(
        {
            "channel": channel.name,
            "reported": sent,
            "inbound": [f"{c.verb}:{c.arg}" for c in inbound] or ["(none)"],
        }
    )
    return 0


def cmd_serve_web(args: argparse.Namespace) -> int:
    """Serve the read-only web panel (progress, task history, approvals).

    The panel opens the store read-only and never starts runs; its one write is
    appending approval verbs to the channel inbox for the will loop to poll. It
    binds localhost by default — reaching it from elsewhere should go through an
    SSH tunnel rather than a public bind. Requires the [web] extra."""
    try:
        import uvicorn

        from yizhi.web.app import create_app
    except ImportError:
        print('web extras missing — install with: python3 -m pip install -e ".[web]"')
        return 1
    config = load_channel_config()
    if args.channel_root:
        config = replace(config, root=args.channel_root)
    app = create_app(db_path=args.db, channel_root=config.root, packet_path=args.packet)
    _print_kv({"panel": f"http://{args.host}:{args.port}", "db": args.db, "channel root": config.root})
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_eval_loops(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    evals = list_loop_evals(db_path, limit=args.limit)
    for event in evals:
        print(json.dumps(event["payload"], ensure_ascii=False))
    return 0


def cmd_funding_dataset(args: argparse.Namespace) -> int:
    result = ingest_cache(args.cache, args.ledger)
    report = build_coverage_report(args.ledger, min_periods=args.min_periods)
    write_coverage_report(report, args.coverage)
    queue_result = build_and_write_queue(args.coverage, args.queue) if args.with_queue else None
    _print_kv(
        {
            "source_snapshot_id": result.source_snapshot_id,
            "symbols": result.symbols_seen,
            "records seen": result.records_seen,
            "records added": result.records_added,
            "records existing": result.records_existing,
            "backtest ready": f"{report['backtest_ready_symbols']}/{report['symbols']}",
            "ledger": result.ledger_path,
            "coverage": args.coverage,
            "queue": queue_result.queue_path if queue_result else "not_run",
            "experiments": queue_result.experiments if queue_result else "not_run",
        }
    )
    return 0


def cmd_funding_queue(args: argparse.Namespace) -> int:
    result = build_and_write_queue(
        args.coverage,
        args.queue,
        min_overlap=args.min_overlap,
        max_symbols=args.max_symbols,
    )
    _print_kv(
        {
            "symbols": result.symbols,
            "experiments": result.experiments,
            "coverage": result.source_coverage_path,
            "queue": result.queue_path,
        }
    )
    return 0


def cmd_funding_run_queue(args: argparse.Namespace) -> int:
    result = execute_experiment_queue(
        args.queue,
        args.results,
        arbbot_root=args.arbbot_root,
        funding_cache=args.funding_cache,
        max_experiments=args.max_experiments,
        only_missing=not args.rerun_existing,
    )
    _print_kv(
        {
            "seen": result.seen,
            "executed": result.executed,
            "skipped": result.skipped,
            "denied": result.denied,
            "failed": result.failed,
            "judged": result.judged,
            "promote": result.promote,
            "kill": result.kill,
            "iterate": result.iterate,
            "insufficient": result.insufficient,
            "results": result.results_path,
        }
    )
    return 0


def cmd_funding_packet(args: argparse.Namespace) -> int:
    result = build_and_write_packet(args.results, args.packet)
    _print_kv(
        {
            "results": result.results,
            "symbols": result.symbols,
            "decisions": result.decisions,
            "packet_id": result.packet_id,
            "packet": result.packet_path,
        }
    )
    return 0


def cmd_campaign_create_btc(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    campaign = build_btc_campaign(campaign_id=args.id, workspace_root=args.workspace_root)
    save_campaign_started(db_path, campaign)
    _print_kv(
        {
            "campaign_id": campaign.id,
            "title": campaign.title,
            "status": campaign.status,
            "cursor": campaign.cursor,
            "stages": [f"{s.id}: {s.title}" for s in campaign.stages],
            "workspace": campaign.workspace_root,
        }
    )
    return 0


def cmd_campaign_run(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    campaign = load_campaign(db_path, args.id)
    if campaign is None:
        print(f"campaign not found: {args.id}")
        return 1
    last = None
    for _ in range(args.max_ticks):
        last = campaign_tick(db_path, campaign, worker=args.worker)
        campaign = last.campaign
        if last.status in {"completed", "paused", "not_active", "task_denied", "deliverable_rejected"}:
            break
    _print_kv(
        {
            "campaign_id": campaign.id,
            "status": campaign.status,
            "cursor": campaign.cursor,
            "last_tick": last.status if last else "not_run",
            "stage_id": last.stage_id if last else "n/a",
            "task_run_id": last.task_run_id if last else "n/a",
            "deliverable_id": last.deliverable_id if last else "n/a",
            "message": last.message if last else "",
        }
    )
    return 0


def cmd_campaign_state(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    campaign = load_campaign(db_path, args.id)
    if campaign is None:
        print(f"campaign not found: {args.id}")
        return 1
    print(campaign.model_dump_json(indent=2))
    return 0


def cmd_campaign_revisit(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    campaign = load_campaign(db_path, args.id)
    if campaign is None:
        print(f"campaign not found: {args.id}")
        return 1
    try:
        campaign = revisit_stage(db_path, campaign, stage_id=args.stage, note=args.note)
    except ValueError as exc:
        print(str(exc))
        return 1
    _print_kv(
        {
            "campaign_id": campaign.id,
            "status": campaign.status,
            "cursor": campaign.cursor,
            "stage": args.stage,
            "note": args.note,
        }
    )
    return 0


def cmd_patch_propose(args: argparse.Namespace) -> int:
    """R1: draft a patch through the governed delegation chain. Never applies —
    review with `git apply --check <artifact>` and apply manually (R4 later)."""
    from yizhi.engine.patches import propose_patch_via_delegation
    from yizhi.state.snapshots import load_or_create_state as _load_state
    from yizhi.state.store import create_snapshot

    db_path = init_db(args.db)
    state = _load_state(db_path)
    client = CliHarnessDelegationClient(load_delegation_config())
    outcome, validation, artifact = propose_patch_via_delegation(
        args.instruction,
        cwd=args.cwd,
        client=client,
        budget=state.budget,
        db_path=db_path,
    )
    state.budget = outcome.budget
    create_snapshot(state, path=db_path)
    _print_kv(
        {
            "policy decision": outcome.gate.decision,
            "validation": "passed" if validation["passed"] else "; ".join(validation["errors"]),
            "files": validation["files"],
            "diff": f"+{validation['additions']} -{validation['deletions']}",
            "artifact": artifact or "n/a",
            "review": f"git apply --check {artifact}" if artifact else "n/a",
            "budget": f"{state.budget.balance:.1f}",
        }
    )
    return 0 if artifact else 1


def cmd_chat(args: argparse.Namespace) -> int:
    from yizhi.liaison.chat import run_chat

    db_path = init_db(args.db)
    return run_chat(
        db_path,
        campaign_id=args.campaign_id,
        worker=args.worker,
    )


def cmd_campaign_adopt(args: argparse.Namespace) -> int:
    """ADR-004 B2: bind a campaign to the will as its pursued goal.

    The campaign is the source of truth; the plan is its projection — one step
    per stage, each targeting the governed tick sentinel. After adopting,
    `will step --env campaign` drives the campaign through the full will loop
    (memory, budget, judgment) instead of the bare state machine."""
    from yizhi.core.schemas import Goal, Plan, PlanStep, PlanStepStatus
    from yizhi.policy.gates import CAMPAIGN_SENTINEL
    from yizhi.state.store import create_snapshot

    db_path = init_db(args.db)
    campaign = load_campaign(db_path, args.id)
    if campaign is None:
        print(f"campaign not found: {args.id}")
        return 1
    state = load_or_create_state(db_path)
    goal = Goal(
        title=f"Campaign: {campaign.title}",
        description=campaign.vision,
        priority=90,
        metadata={"campaign_id": campaign.id},
    )
    steps = [
        PlanStep(
            description=f"{stage.id} {stage.title}: {stage.objective}",
            target_command=[CAMPAIGN_SENTINEL, "tick", campaign.id],
            target_title=f"Campaign tick: advance {stage.id} {stage.title}",
            status=PlanStepStatus.DONE if index < campaign.cursor else PlanStepStatus.PENDING,
        )
        for index, stage in enumerate(campaign.stages)
    ]
    plan = Plan(goal_id=goal.id, steps=steps, cursor=min(campaign.cursor, len(steps)))
    state.goals = [goal]
    state.active_plan = plan
    append_event(EventType.GOAL_SET, aggregate_type="goal", aggregate_id=goal.id, payload=goal,
                 correlation_id=campaign.id, path=db_path)
    append_event(EventType.PLAN_CREATED, aggregate_type="plan", aggregate_id=plan.id, payload=plan,
                 correlation_id=campaign.id, path=db_path)
    create_snapshot(state, path=db_path)
    _print_kv(
        {
            "campaign_id": campaign.id,
            "goal_id": goal.id,
            "goal": goal.title,
            "plan_id": plan.id,
            "plan_steps": len(plan.steps),
            "plan_cursor": plan.cursor,
            "next": f"will step --env campaign --campaign-id {campaign.id}",
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="will", description="Local governed Will Agent v0")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite event store path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the local event store")
    init_parser.set_defaults(func=cmd_init)

    observe_parser = subparsers.add_parser("observe", help="Observe an environment")
    observe_parser.add_argument("--env", choices=["self", "self_repo", "arbbot"], required=True)
    observe_parser.add_argument("--root", default=None)
    observe_parser.set_defaults(func=cmd_observe)

    step_parser = subparsers.add_parser("step", help="Run one bounded will loop")
    step_parser.add_argument("--env", choices=["self", "self_repo", "arbbot", "campaign"], required=True)
    step_parser.add_argument("--campaign-id", default="btc-mvp", help="Campaign id for --env campaign")
    step_parser.add_argument("--worker", default="fake", help="Campaign worker for --env campaign (fake/claude/codex)")
    step_parser.add_argument("--root", default=None)
    step_parser.set_defaults(func=cmd_step)

    run_parser = subparsers.add_parser("run", help="Run the will loop continuously until a stop condition")
    run_parser.add_argument("--env", choices=["self", "self_repo", "arbbot", "campaign"], required=True)
    run_parser.add_argument("--campaign-id", default="btc-mvp", help="Campaign id for --env campaign")
    run_parser.add_argument("--worker", default="fake", help="Campaign worker for --env campaign (fake/claude/codex)")
    run_parser.add_argument("--root", default=None)
    run_parser.add_argument("--max-steps", type=int, default=50, help="Structural ceiling (always applies)")
    run_parser.add_argument("--vision", default=None, help="Seed/override the standing north-star vision")
    run_parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to pause between steps (rate politeness)")
    run_parser.add_argument("--no-stuck-stop", action="store_true", help="Disable semantic stuck-detection halt")
    run_parser.add_argument(
        "--channel-root",
        default=None,
        help="Enable the dialogue seam: drain this channel inbox each step (web chat / IM commands)",
    )
    run_parser.add_argument(
        "--fetch-on-exhaust",
        action="store_true",
        help="On frontier exhaustion, fetch deeper/broader funding data via the VPS and continue "
        "instead of halting (A6; opt-in, needs VPS access). run_step still never SSHes.",
    )
    run_parser.set_defaults(func=cmd_run)

    events_parser = subparsers.add_parser("events", help="Print recent events")
    events_parser.add_argument("--limit", type=int, default=20)
    events_parser.set_defaults(func=cmd_events)

    state_parser = subparsers.add_parser("state", help="Print latest WillState snapshot")
    state_parser.set_defaults(func=cmd_state)

    delegate_parser = subparsers.add_parser(
        "delegate", help="Run one governed read-only delegation to a coding harness (R0)"
    )
    delegate_parser.add_argument(
        "--kind", choices=[k.value for k in DelegationKind], default=DelegationKind.ANALYZE_REPO.value
    )
    delegate_parser.add_argument("--instruction", required=True, help="Read-only brief for the harness")
    delegate_parser.add_argument("--cwd", required=True, help="Restricted in-repo relative path the harness may read")
    delegate_parser.add_argument("--allowed-tools", default="", help="Comma-separated read-only tools; default from config")
    delegate_parser.set_defaults(func=cmd_delegate)

    report_parser = subparsers.add_parser(
        "report", help="Report reportable events to the configured channel and drain inbound commands (R2)"
    )
    report_parser.add_argument("--limit", type=int, default=20, help="How many recent events to scan")
    report_parser.add_argument("--channel-root", default="", help="Override the local_inbox directory")
    report_parser.set_defaults(func=cmd_report)

    serve_web_parser = subparsers.add_parser(
        "serve-web", help="Serve the read-only web panel (progress, task history, approvals)"
    )
    serve_web_parser.add_argument("--host", default="127.0.0.1", help="Bind address (keep localhost; tunnel for remote)")
    serve_web_parser.add_argument("--port", type=int, default=8321)
    serve_web_parser.add_argument("--channel-root", default=None, help="Override channel root for approval inbox writes")
    serve_web_parser.add_argument(
        "--packet", default="data/funding/promotion_packet.json", help="Promotion packet path for the deliverables page"
    )
    serve_web_parser.set_defaults(func=cmd_serve_web)

    eval_parser = subparsers.add_parser("eval", help="Evaluation commands")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)
    loops_parser = eval_subparsers.add_parser("loops", help="Print loop eval events")
    loops_parser.add_argument("--limit", type=int, default=20)
    loops_parser.set_defaults(func=cmd_eval_loops)

    funding_parser = subparsers.add_parser("funding", help="FundArb data commands")
    funding_subparsers = funding_parser.add_subparsers(dest="funding_command", required=True)
    dataset_parser = funding_subparsers.add_parser("dataset", help="Build append-only funding ledger and coverage report")
    dataset_parser.add_argument("--cache", default="data/funding_cache.json", help="Input funding cache JSON")
    dataset_parser.add_argument("--ledger", default="data/funding/ledger.jsonl", help="Append-only output ledger JSONL")
    dataset_parser.add_argument("--coverage", default="data/funding/coverage.json", help="Coverage report JSON")
    dataset_parser.add_argument("--queue", default="data/funding/experiment_queue.json", help="Output experiment queue JSON")
    dataset_parser.add_argument("--min-periods", type=int, default=20, help="Minimum overlapping periods for readiness")
    dataset_parser.add_argument("--with-queue", action="store_true", help="Also rebuild the deterministic experiment queue")
    dataset_parser.set_defaults(func=cmd_funding_dataset)

    queue_parser = funding_subparsers.add_parser("queue", help="Build deterministic funding-diff experiment queue")
    queue_parser.add_argument("--coverage", default="data/funding/coverage.json", help="Input coverage report JSON")
    queue_parser.add_argument("--queue", default="data/funding/experiment_queue.json", help="Output experiment queue JSON")
    queue_parser.add_argument("--min-overlap", type=int, default=None, help="Override minimum overlapping periods")
    queue_parser.add_argument("--max-symbols", type=int, default=None, help="Limit symbols after priority sorting")
    queue_parser.set_defaults(func=cmd_funding_queue)

    run_queue_parser = funding_subparsers.add_parser("run-queue", help="Execute queued funding-diff experiments")
    run_queue_parser.add_argument("--queue", default="data/funding/experiment_queue.json", help="Input experiment queue JSON")
    run_queue_parser.add_argument("--results", default="data/funding/experiment_results.jsonl", help="Append-only output results JSONL")
    run_queue_parser.add_argument("--arbbot-root", default="/Users/griffith/Projects/AI/ArbBot", help="ArbBot repository root")
    run_queue_parser.add_argument("--funding-cache", default="data/funding_cache.json", help="Local funding cache JSON")
    run_queue_parser.add_argument("--max-experiments", type=int, default=None, help="Maximum new queue items to execute")
    run_queue_parser.add_argument("--rerun-existing", action="store_true", help="Append another result even when result_id exists")
    run_queue_parser.set_defaults(func=cmd_funding_run_queue)

    packet_parser = funding_subparsers.add_parser("packet", help="Build FundArb promotion/kill packet from results")
    packet_parser.add_argument("--results", default="data/funding/experiment_results.jsonl", help="Input experiment results JSONL")
    packet_parser.add_argument("--packet", default="data/funding/promotion_packet.json", help="Output promotion packet JSON")
    packet_parser.set_defaults(func=cmd_funding_packet)

    campaign_parser = subparsers.add_parser("campaign", help="Long-horizon campaign harness commands")
    campaign_subparsers = campaign_parser.add_subparsers(dest="campaign_command", required=True)

    create_btc_parser = campaign_subparsers.add_parser("create-btc", help="Create the deterministic BTC MVP campaign")
    create_btc_parser.add_argument("--id", default="btc-mvp", help="Campaign id")
    create_btc_parser.add_argument("--workspace-root", default="data/campaigns", help="Local campaign artifact root")
    create_btc_parser.set_defaults(func=cmd_campaign_create_btc)

    campaign_run_parser = campaign_subparsers.add_parser("run", help="Run bounded campaign ticks")
    campaign_run_parser.add_argument("--id", required=True, help="Campaign id")
    campaign_run_parser.add_argument("--max-ticks", type=int, default=1, help="Maximum deterministic campaign ticks")
    campaign_run_parser.add_argument(
        "--worker",
        default="fake",
        help="Worker: fake (deterministic), or claude/codex (real research via manual-gated delegation config)",
    )
    campaign_run_parser.set_defaults(func=cmd_campaign_run)

    campaign_state_parser = campaign_subparsers.add_parser("state", help="Print projected campaign state")
    campaign_state_parser.add_argument("--id", required=True, help="Campaign id")
    campaign_state_parser.set_defaults(func=cmd_campaign_state)

    campaign_adopt_parser = campaign_subparsers.add_parser(
        "adopt", help="Bind a campaign to the will as its pursued goal (plan projected from stages)"
    )
    campaign_adopt_parser.add_argument("--id", required=True, help="Campaign id")
    campaign_adopt_parser.set_defaults(func=cmd_campaign_adopt)

    chat_parser = subparsers.add_parser(
        "chat", help="Interactive chat with the will (governed dialogue + /research delegation)"
    )
    chat_parser.add_argument("--campaign-id", default=None, help="Chat in a campaign's context (default: adopted campaign, else self)")
    chat_parser.add_argument("--worker", default="fake", help="Campaign worker for in-chat ticks (fake/claude/codex)")
    chat_parser.set_defaults(func=cmd_chat)

    patch_parser = subparsers.add_parser("patch", help="R1 governed patch drafting (never applies)")
    patch_subparsers = patch_parser.add_subparsers(dest="patch_command", required=True)
    patch_propose_parser = patch_subparsers.add_parser("propose", help="Draft one patch via the coding-harness worker")
    patch_propose_parser.add_argument("--instruction", required=True, help="What the patch should change")
    patch_propose_parser.add_argument("--cwd", default=".", help="Restricted in-repo directory the worker may read (default: repo root, so diff paths are root-relative)")
    patch_propose_parser.set_defaults(func=cmd_patch_propose)

    campaign_revisit_parser = campaign_subparsers.add_parser("revisit", help="Revisit a campaign stage")
    campaign_revisit_parser.add_argument("--id", required=True, help="Campaign id")
    campaign_revisit_parser.add_argument("--stage", required=True, help="Stage id, e.g. S1")
    campaign_revisit_parser.add_argument("--note", required=True, help="Revision note for the rerun")
    campaign_revisit_parser.set_defaults(func=cmd_campaign_revisit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
