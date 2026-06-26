"""Command line interface for yizhi Will Agent v0."""

from __future__ import annotations

import argparse
import json
from typing import Any

from yizhi.core.ids import new_id
from yizhi.core.schemas import EventType, WillState
from yizhi.engine.loop import environment_from_name, run_step
from yizhi.engine.runner import run_until
from yizhi.eval.loops import list_loop_evals
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
    env = environment_from_name(args.env, args.root)
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
    """A6 frontier-widening hook for `yizhi run --fetch-on-exhaust`. On exhaustion the
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
    env = environment_from_name(args.env, args.root)

    def on_step(n: int, result: Any, st: WillState) -> None:
        print(f"step {n:>3}: status={result.loop_status} action={result.proposal_id} budget={st.budget.balance:.1f}")

    fetch_hook = _make_vps_fetch_hook() if getattr(args, "fetch_on_exhaust", False) else None
    outcome = run_until(
        env,
        state,
        db_path,
        max_steps=args.max_steps,
        stop_on_stuck=not args.no_stuck_stop,
        sleep=args.sleep,
        on_step=on_step,
        fetch_hook=fetch_hook,
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


def cmd_eval_loops(args: argparse.Namespace) -> int:
    db_path = init_db(args.db)
    evals = list_loop_evals(db_path, limit=args.limit)
    for event in evals:
        print(json.dumps(event["payload"], ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yizhi", description="Local governed Will Agent v0")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite event store path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the local event store")
    init_parser.set_defaults(func=cmd_init)

    observe_parser = subparsers.add_parser("observe", help="Observe an environment")
    observe_parser.add_argument("--env", choices=["self", "self_repo", "arbbot"], required=True)
    observe_parser.add_argument("--root", default=None)
    observe_parser.set_defaults(func=cmd_observe)

    step_parser = subparsers.add_parser("step", help="Run one bounded will loop")
    step_parser.add_argument("--env", choices=["self", "self_repo", "arbbot"], required=True)
    step_parser.add_argument("--root", default=None)
    step_parser.set_defaults(func=cmd_step)

    run_parser = subparsers.add_parser("run", help="Run the will loop continuously until a stop condition")
    run_parser.add_argument("--env", choices=["self", "self_repo", "arbbot"], required=True)
    run_parser.add_argument("--root", default=None)
    run_parser.add_argument("--max-steps", type=int, default=50, help="Structural ceiling (always applies)")
    run_parser.add_argument("--vision", default=None, help="Seed/override the standing north-star vision")
    run_parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to pause between steps (rate politeness)")
    run_parser.add_argument("--no-stuck-stop", action="store_true", help="Disable semantic stuck-detection halt")
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

    eval_parser = subparsers.add_parser("eval", help="Evaluation commands")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)
    loops_parser = eval_subparsers.add_parser("loops", help="Print loop eval events")
    loops_parser.add_argument("--limit", type=int, default=20)
    loops_parser.set_defaults(func=cmd_eval_loops)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
