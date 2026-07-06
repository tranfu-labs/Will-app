"""Command line interface for the local Will Harness Kernel."""

from __future__ import annotations

import argparse
import json
from typing import Any

from will.campaigns.btc import build_btc_campaign
from will.campaigns.engine import campaign_tick, revisit_stage
from will.campaigns.store import load_campaign, save_campaign_started
from will.config import load_delegation_config
from will.core.schemas import DelegationKind, DelegationTask, WillState
from will.workers.delegation import CliHarnessDelegationClient, build_delegation_proposal, execute_delegation
from will.ledger.snapshots import load_or_create_state
from will.ledger.store import DEFAULT_DB_PATH, init_db, list_events, load_latest_snapshot


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

    Manual entry point for governed external worker delegation. The harness is OFF unless
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
    """Draft a patch through the governed delegation chain. Never applies;
    review with `git apply --check <artifact>` and apply manually."""
    from will.workers.patches import propose_patch_via_delegation
    from will.ledger.snapshots import load_or_create_state as _load_state
    from will.ledger.store import create_snapshot

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="will", description="Local Will Harness Kernel")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite event store path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the local event store")
    init_parser.set_defaults(func=cmd_init)

    events_parser = subparsers.add_parser("events", help="Print recent events")
    events_parser.add_argument("--limit", type=int, default=20)
    events_parser.set_defaults(func=cmd_events)

    state_parser = subparsers.add_parser("state", help="Print latest WillState snapshot")
    state_parser.set_defaults(func=cmd_state)

    delegate_parser = subparsers.add_parser(
        "delegate", help="Run one governed read-only delegation to a coding harness"
    )
    delegate_parser.add_argument(
        "--kind", choices=[k.value for k in DelegationKind], default=DelegationKind.ANALYZE_REPO.value
    )
    delegate_parser.add_argument("--instruction", required=True, help="Read-only brief for the harness")
    delegate_parser.add_argument("--cwd", required=True, help="Restricted in-repo relative path the harness may read")
    delegate_parser.add_argument("--allowed-tools", default="", help="Comma-separated read-only tools; default from config")
    delegate_parser.set_defaults(func=cmd_delegate)

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

    patch_parser = subparsers.add_parser("patch", help="Governed patch drafting (never applies)")
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
